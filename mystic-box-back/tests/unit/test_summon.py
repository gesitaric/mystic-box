import json

import pytest
from botocore.exceptions import ClientError
from mystic_shared import cards, summon_token

from get_summon_status import app as get_summon_status
from open_box import app as open_box
from save_user_card import app as save_user_card

from tests.unit.fake_dynamo import FakeDynamo

NOW = 10_000
USER = "user-123"
COOLDOWN = 3600


def summon_body(file_names=("rowan.jfif", "kaito.jfif", "astra.jfif"), now=NOW, user=USER):
    return json.dumps({"summonToken": summon_token.issue(file_names, user, now=now)})


# ---------- Definições das cartas ----------


def test_every_rarity_has_a_valid_listing_price_range():
    for character in cards.CHARACTERS:
        price_range = cards.listing_price_range(character)
        assert 0 < price_range["min"] <= price_range["max"]


def test_listing_price_validation():
    astra = cards.get_character("astra.jfif")
    limits = cards.LISTING_PRICE_LIMITS[5]
    assert cards.is_valid_listing_price(astra, limits["min"])
    assert cards.is_valid_listing_price(astra, limits["max"])
    assert not cards.is_valid_listing_price(astra, limits["min"] - 1)
    assert not cards.is_valid_listing_price(astra, limits["max"] + 1)
    assert not cards.is_valid_listing_price(astra, float(limits["min"]))
    assert not cards.is_valid_listing_price(astra, True)
    assert not cards.is_valid_listing_price(None, limits["min"])


def test_max_listing_quantity():
    astra = cards.get_character("astra.jfif")
    assert cards.max_listing_quantity(astra, 3) == 3
    assert cards.max_listing_quantity(astra, 500) == cards.MAX_LISTING_QUANTITY
    assert cards.max_listing_quantity(None, 3) == 0


def test_file_names_are_unique():
    file_names = [character["file_name"] for character in cards.CHARACTERS]
    assert len(set(file_names)) == len(file_names)


def test_get_character():
    assert cards.get_character("astra.jfif")["name"] == "Astra"
    assert cards.get_character("nao-existe.jfif") is None


def test_draw_cards_never_repeat():
    for _ in range(500):
        names = [card["name"] for card in cards.draw_cards()]
        assert len(set(names)) == 3


def test_draw_cards_last_card_uses_boosted_weights(monkeypatch):
    calls = []

    def fake_choices(population, weights, k):
        calls.append(dict(zip((c["name"] for c in population), weights)))
        return [population[0]]

    monkeypatch.setattr(cards.random, "choices", fake_choices)
    cards.draw_cards()

    assert len(calls) == 3
    # Os dois primeiros sorteios usam os pesos normais; o último, os reforçados.
    assert calls[0]["Astra"] == cards.RARITY_WEIGHTS[5]
    assert calls[1]["Astra"] == cards.RARITY_WEIGHTS[5]
    assert calls[2]["Astra"] == cards.LAST_CARD_RARITY_WEIGHTS[5]
    assert calls[2]["Kaito"] == cards.LAST_CARD_RARITY_WEIGHTS[4]
    assert calls[2]["Rowan"] == cards.LAST_CARD_RARITY_WEIGHTS[3]
    # Personagens já sorteados saem das opções seguintes.
    assert "Malachar" not in calls[1]
    assert "Boreas" not in calls[2]


# ---------- Token de sorteio ----------


def test_summon_token_round_trip():
    token = summon_token.issue(["astra.jfif"], USER, now=NOW)
    payload = summon_token.verify(token, now=NOW + 1)

    assert payload["cards"] == ["astra.jfif"]
    assert payload["uid"] == USER
    assert payload["iat"] == NOW
    assert payload["exp"] == NOW + summon_token.TOKEN_TTL_SECONDS
    assert payload["id"]


def forge(payload):
    """Token com o conteúdo `payload` e uma assinatura válida para ele."""
    encoded = summon_token._b64encode(json.dumps(payload).encode())
    return f"{encoded}.{summon_token._b64encode(summon_token._sign(encoded))}"


def test_summon_token_rejects_tampered_cards():
    token = summon_token.issue(["rowan.jfif"], USER, now=NOW)
    signature = token.split(".")[1]
    forged = summon_token._b64encode(
        json.dumps(
            {"v": 2, "id": "x", "uid": USER, "cards": ["astra.jfif"],
             "iat": NOW, "exp": NOW + 60}
        ).encode()
    )

    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(f"{forged}.{signature}", now=NOW)


def test_summon_token_rejects_tokens_without_player():
    # Formato antigo (v1), sem o jogador: não é mais aceito.
    old = forge({"v": 1, "id": "x", "cards": ["astra.jfif"], "iat": NOW, "exp": NOW + 60})

    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(old, now=NOW)


def test_summon_token_rejects_other_secret(monkeypatch):
    token = summon_token.issue(["astra.jfif"], USER, now=NOW)
    monkeypatch.setattr(summon_token, "_secret", b"another-secret")

    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(token, now=NOW)


@pytest.mark.parametrize("token", [None, "", "abc", "a.b.c", "!!!.???", 42])
def test_summon_token_rejects_garbage(token):
    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(token, now=NOW)


def test_summon_token_expires():
    token = summon_token.issue(["astra.jfif"], USER, now=NOW)

    with pytest.raises(summon_token.ExpiredSummonToken):
        summon_token.verify(token, now=NOW + summon_token.TOKEN_TTL_SECONDS)


def test_pending_summon_only_for_its_player_while_valid():
    token = summon_token.issue(["astra.jfif"], USER, now=NOW)
    item = {"pendingToken": {"S": token}}

    assert summon_token.pending_summon(item, USER, NOW) == {
        "cards": [{"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}],
        "summonToken": token,
    }
    assert summon_token.pending_summon(item, "someone-else", NOW) is None
    assert summon_token.pending_summon(
        item, USER, NOW + summon_token.TOKEN_TTL_SECONDS
    ) is None
    assert summon_token.pending_summon({}, USER, NOW) is None
    assert summon_token.pending_summon(None, USER, NOW) is None


# ---------- Fluxo da invocação (open_box + save_user_card) ----------


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture()
def summon_db(monkeypatch):
    """Banco em memória e relógio compartilhados pelas Lambdas da invocação."""
    db = FakeDynamo({
        "summon-state": ("userId", None),
        "summon-tokens": ("tokenId", None),
        "user-cards": ("userId", "ownedCardId"),
    })
    clock = Clock()
    for module in (open_box, save_user_card, get_summon_status):
        monkeypatch.setattr(module, "_client", db)
        monkeypatch.setattr(module, "USER_SUMMON_STATE_TABLE", "summon-state")
        monkeypatch.setattr(module, "SUMMON_COOLDOWN_SECONDS", COOLDOWN)
        monkeypatch.setattr(module.time, "time", clock)
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(save_user_card, "SUMMON_TOKENS_TABLE", "summon-tokens")
    monkeypatch.setattr(summon_token.time, "time", clock)
    db.clock = clock
    return db


def open_portal(authenticated_event, user=USER):
    ret = open_box.lambda_handler(authenticated_event(sub=user, httpMethod="POST"), "")
    return ret["statusCode"], json.loads(ret["body"]), ret["headers"]


def keep(authenticated_event, token, user=USER):
    ret = save_user_card.lambda_handler(
        authenticated_event(sub=user, httpMethod="POST",
                            body=json.dumps({"summonToken": token})),
        "",
    )
    return ret["statusCode"], json.loads(ret["body"])


def owned_cards(db, user=USER):
    return [item for (owner, _), item in db.tables["user-cards"].items() if owner == user]


def test_open_box_requires_authentication(apigw_event):
    ret = open_box.lambda_handler(dict(apigw_event, httpMethod="POST"), "")

    assert ret["statusCode"] == 401


def test_open_box_returns_cards_and_signed_token(authenticated_event, summon_db):
    status, data, headers = open_portal(authenticated_event)

    assert status == 200
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert len(data["cards"]) == 3
    # O preço não faz parte do resultado do sorteio.
    assert all(set(card) == {"name", "rarity", "file_name"} for card in data["cards"])

    payload = summon_token.verify(data["summonToken"])
    assert payload["cards"] == [card["file_name"] for card in data["cards"]]
    assert payload["uid"] == USER


def test_open_box_consumes_cooldown_and_keeps_draw_pending(authenticated_event, summon_db):
    _, data, _ = open_portal(authenticated_event)

    state = summon_db.tables["summon-state"][(USER, None)]
    payload = summon_token.verify(data["summonToken"])
    assert state["lastSummonAt"] == {"N": str(NOW)}
    assert state["pendingToken"] == {"S": data["summonToken"]}
    assert state["pendingTokenId"] == {"S": payload["id"]}
    assert state["pendingExpiresAt"] == {"N": str(payload["exp"])}


def test_open_box_again_returns_the_same_draw(authenticated_event, summon_db):
    """Abrir de novo não sorteia outra vez: não dá para escolher a melhor tirada."""
    _, first, _ = open_portal(authenticated_event)
    summon_db.clock.now += 60

    for _ in range(5):
        status, again, _ = open_portal(authenticated_event)
        assert status == 200
        assert again == first


def test_open_box_during_cooldown_draws_nothing(authenticated_event, summon_db):
    _, data, _ = open_portal(authenticated_event)
    assert keep(authenticated_event, data["summonToken"])[0] == 201
    summon_db.clock.now += 600

    status, body, headers = open_portal(authenticated_event)

    assert status == 429
    assert body["retryAfterSeconds"] == COOLDOWN - 600
    assert headers["Retry-After"] == str(COOLDOWN - 600)
    assert "pendingToken" not in summon_db.tables["summon-state"][(USER, None)]


def test_open_box_after_expired_draw_waits_the_cooldown(authenticated_event, summon_db):
    """Não guardar um sorteio e esperar ele expirar não libera outro antes da hora."""
    open_portal(authenticated_event)
    summon_db.clock.now += summon_token.TOKEN_TTL_SECONDS

    status, body, _ = open_portal(authenticated_event)

    assert status == 429
    assert body["retryAfterSeconds"] == COOLDOWN - summon_token.TOKEN_TTL_SECONDS


def test_open_box_after_cooldown_draws_again(authenticated_event, summon_db):
    _, first, _ = open_portal(authenticated_event)
    keep(authenticated_event, first["summonToken"])
    summon_db.clock.now += COOLDOWN

    status, second, _ = open_portal(authenticated_event)

    assert status == 200
    assert second["summonToken"] != first["summonToken"]
    state = summon_db.tables["summon-state"][(USER, None)]
    assert state["lastSummonAt"] == {"N": str(NOW + COOLDOWN)}


def test_open_box_concurrent_requests_share_one_draw(authenticated_event, summon_db, monkeypatch):
    """Outro pedido grava o sorteio entre a leitura e a gravação deste."""
    _, rival, _ = open_portal(authenticated_event)
    state = summon_db.tables["summon-state"].pop((USER, None))
    real_store = open_box.store_pending

    def racing_store(*args):
        summon_db.tables["summon-state"][(USER, None)] = state
        return real_store(*args)

    monkeypatch.setattr(open_box, "store_pending", racing_store)

    status, data, _ = open_portal(authenticated_event)

    assert status == 200
    assert data == rival
    assert summon_db.tables["summon-state"][(USER, None)] == state


def test_open_box_handles_dynamodb_error(authenticated_event, summon_db, monkeypatch):
    def broken(**_):
        raise ClientError({"Error": {"Code": "500"}}, "GetItem")

    monkeypatch.setattr(summon_db, "get_item", broken)

    status, _, _ = open_portal(authenticated_event)

    assert status == 500


def test_save_user_card_stores_cards_from_pending_draw(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event)
    summon_db.clock.now += 20

    status, data = keep(authenticated_event, drawn["summonToken"])

    assert status == 201
    assert [card["name"] for card in data["cards"]] == [c["name"] for c in drawn["cards"]]
    assert all(card["userId"] == USER for card in data["cards"])
    assert len({card["ownedCardId"] for card in data["cards"]}) == 3
    # O tempo de espera começou ao abrir o portal.
    assert data["retryAfterSeconds"] == COOLDOWN - 20

    stored = owned_cards(summon_db)
    assert sorted(item["file_name"]["S"] for item in stored) == sorted(
        card["file_name"] for card in drawn["cards"]
    )
    # O preço não é gravado na carta: é sempre lido das definições.
    assert all("price" not in item for item in stored)
    state = summon_db.tables["summon-state"][(USER, None)]
    assert "pendingToken" not in state and "pendingTokenId" not in state
    assert state["lastSummonAt"] == {"N": str(NOW)}
    payload = summon_token.verify(drawn["summonToken"])
    assert summon_db.tables["summon-tokens"][(payload["id"], None)]["expiresAt"] == {
        "N": str(payload["exp"])
    }


def test_save_user_card_ignores_cards_sent_by_client(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event)
    body = json.dumps(
        {
            "cards": [{"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif"}],
            "summonToken": drawn["summonToken"],
        }
    )

    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=body), ""
    )

    assert ret["statusCode"] == 201
    assert [card["name"] for card in json.loads(ret["body"])["cards"]] == [
        card["name"] for card in drawn["cards"]
    ]


def test_save_user_card_rejects_reused_token(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event)
    keep(authenticated_event, drawn["summonToken"])

    status, _ = keep(authenticated_event, drawn["summonToken"])

    assert status == 409
    assert len(owned_cards(summon_db)) == 3


def test_save_user_card_rejects_token_of_another_player(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event, user="friend")

    status, _ = keep(authenticated_event, drawn["summonToken"])

    assert status == 400
    assert owned_cards(summon_db) == []
    # O sorteio continua pendente para o dono.
    assert keep(authenticated_event, drawn["summonToken"], user="friend")[0] == 201


def test_save_user_card_rejects_signed_draw_that_is_not_pending(authenticated_event, summon_db):
    """Um token válido que não é o sorteio pendente do jogador não vale."""
    open_portal(authenticated_event)

    status, data = keep(authenticated_event, json.loads(summon_body())["summonToken"])

    assert status == 409
    assert data["message"] == "This summon is no longer valid."
    assert owned_cards(summon_db) == []


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        json.dumps([]),
        json.dumps({}),
        # Formato antigo: cartas enviadas pelo cliente não são mais aceitas.
        json.dumps({"cards": [{"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}]}),
        json.dumps({"summonToken": "forjado.assinatura"}),
    ],
)
def test_save_user_card_rejects_invalid_body(authenticated_event, summon_db, body):
    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=body), ""
    )

    assert ret["statusCode"] == 400
    assert owned_cards(summon_db) == []


@pytest.mark.parametrize(
    "file_names",
    [
        ("astra.jfif", "astra.jfif"),
        ("rowan.jfif", "corvus.jfif", "kaito.jfif", "sylva.jfif"),
        ("nao-existe.jfif",),
        (),
    ],
)
def test_save_user_card_rejects_invalid_draws(authenticated_event, summon_db, file_names):
    status, _ = keep(authenticated_event, json.loads(summon_body(file_names))["summonToken"])

    assert status == 400
    assert owned_cards(summon_db) == []


def test_save_user_card_rejects_expired_token(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event)
    summon_db.clock.now += summon_token.TOKEN_TTL_SECONDS

    status, _ = keep(authenticated_event, drawn["summonToken"])

    assert status == 410
    assert owned_cards(summon_db) == []


def test_save_user_card_handles_dynamodb_error(authenticated_event, summon_db, monkeypatch):
    _, drawn, _ = open_portal(authenticated_event)

    def broken(**_):
        raise ClientError({"Error": {"Code": "500"}}, "TransactWriteItems")

    monkeypatch.setattr(summon_db, "transact_write_items", broken)

    status, _ = keep(authenticated_event, drawn["summonToken"])

    assert status == 500


def test_summon_status_returns_pending_draw(authenticated_event, summon_db):
    _, drawn, _ = open_portal(authenticated_event)
    summon_db.clock.now += 100

    ret = get_summon_status.lambda_handler(authenticated_event(), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["retryAfterSeconds"] == COOLDOWN - 100
    assert data["pendingSummon"] == drawn

    keep(authenticated_event, drawn["summonToken"])
    ret = get_summon_status.lambda_handler(authenticated_event(), "")
    assert json.loads(ret["body"])["pendingSummon"] is None
