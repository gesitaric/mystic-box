import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mystic_shared import cards, summon_token

from open_box import app as open_box
from save_user_card import app as save_user_card

NOW = 10_000


def transaction_conflict(*failed_indexes, size=5):
    return ClientError(
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed" if i in failed_indexes else "None"}
                for i in range(size)
            ],
        },
        "TransactWriteItems",
    )


def summon_body(file_names=("rowan.jfif", "kaito.jfif", "astra.jfif"), now=NOW):
    return json.dumps({"summonToken": summon_token.issue(file_names, now=now)})


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
    token = summon_token.issue(["astra.jfif"], now=NOW)
    payload = summon_token.verify(token, now=NOW + 1)

    assert payload["cards"] == ["astra.jfif"]
    assert payload["exp"] == NOW + summon_token.TOKEN_TTL_SECONDS
    assert payload["id"]


def test_summon_token_rejects_tampered_cards():
    token = summon_token.issue(["rowan.jfif"], now=NOW)
    signature = token.split(".")[1]
    forged = summon_token._b64encode(
        json.dumps(
            {"v": 1, "id": "x", "cards": ["astra.jfif"], "iat": NOW, "exp": NOW + 60}
        ).encode()
    )

    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(f"{forged}.{signature}", now=NOW)


def test_summon_token_rejects_other_secret(monkeypatch):
    token = summon_token.issue(["astra.jfif"], now=NOW)
    monkeypatch.setattr(summon_token, "_secret", b"another-secret")

    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(token, now=NOW)


@pytest.mark.parametrize("token", [None, "", "abc", "a.b.c", "!!!.???", 42])
def test_summon_token_rejects_garbage(token):
    with pytest.raises(summon_token.InvalidSummonToken):
        summon_token.verify(token, now=NOW)


def test_summon_token_expires():
    token = summon_token.issue(["astra.jfif"], now=NOW)

    with pytest.raises(summon_token.ExpiredSummonToken):
        summon_token.verify(token, now=NOW + summon_token.TOKEN_TTL_SECONDS)


# ---------- open_box ----------


def test_open_box_returns_cards_and_signed_token(apigw_event):
    ret = open_box.lambda_handler(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert len(data["cards"]) == 3
    # O preço não faz parte do resultado do sorteio.
    assert all(set(card) == {"name", "rarity", "file_name"} for card in data["cards"])

    payload = summon_token.verify(data["summonToken"])
    assert payload["cards"] == [card["file_name"] for card in data["cards"]]


# ---------- save_user_card ----------


@pytest.fixture()
def save_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(save_user_card, "_client", client)
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(save_user_card, "USER_SUMMON_STATE_TABLE", "summon-state")
    monkeypatch.setattr(save_user_card, "SUMMON_TOKENS_TABLE", "summon-tokens")
    monkeypatch.setattr(save_user_card, "SUMMON_COOLDOWN_SECONDS", 3600)
    monkeypatch.setattr(save_user_card.time, "time", lambda: NOW)
    monkeypatch.setattr(summon_token.time, "time", lambda: NOW)
    return client


def save(authenticated_event, body):
    return save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=body), ""
    )


def test_save_user_card_stores_cards_from_token(authenticated_event, save_client):
    ret = save(authenticated_event, summon_body())
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert [card["name"] for card in data["cards"]] == ["Rowan", "Kaito", "Astra"]
    assert all(card["userId"] == "user-123" for card in data["cards"])
    assert len({card["ownedCardId"] for card in data["cards"]}) == 3
    assert data["retryAfterSeconds"] == 3600

    update, token_put, *puts = save_client.transact_write_items.call_args.kwargs[
        "TransactItems"
    ]
    assert update["Update"]["TableName"] == "summon-state"
    assert update["Update"]["ExpressionAttributeValues"] == {
        ":now": {"N": "10000"},
        ":threshold": {"N": "6400"},
    }
    assert token_put["Put"]["TableName"] == "summon-tokens"
    assert token_put["Put"]["ConditionExpression"] == "attribute_not_exists(tokenId)"
    assert token_put["Put"]["Item"]["expiresAt"] == {
        "N": str(NOW + summon_token.TOKEN_TTL_SECONDS)
    }
    assert len(puts) == 3
    assert puts[2]["Put"]["TableName"] == "user-cards"
    assert puts[2]["Put"]["Item"]["name"] == {"S": "Astra"}
    assert puts[2]["Put"]["Item"]["rarity"] == {"N": "5"}
    assert puts[2]["Put"]["Item"]["file_name"] == {"S": "astra.jfif"}
    # O preço não é gravado na carta: é sempre lido das definições.
    assert "price" not in puts[2]["Put"]["Item"]


def test_save_user_card_ignores_cards_sent_by_client(authenticated_event, save_client):
    body = json.dumps(
        {
            "cards": [{"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif"}],
            "summonToken": summon_token.issue(["rowan.jfif"], now=NOW),
        }
    )

    ret = save(authenticated_event, body)

    assert ret["statusCode"] == 201
    assert [card["name"] for card in json.loads(ret["body"])["cards"]] == ["Rowan"]


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
def test_save_user_card_rejects_invalid_body(authenticated_event, save_client, body):
    ret = save(authenticated_event, body)

    assert ret["statusCode"] == 400
    save_client.transact_write_items.assert_not_called()


@pytest.mark.parametrize(
    "file_names",
    [
        ("astra.jfif", "astra.jfif"),
        ("rowan.jfif", "corvus.jfif", "kaito.jfif", "sylva.jfif"),
        ("nao-existe.jfif",),
        (),
    ],
)
def test_save_user_card_rejects_invalid_draws(authenticated_event, save_client, file_names):
    ret = save(authenticated_event, summon_body(file_names))

    assert ret["statusCode"] == 400
    save_client.transact_write_items.assert_not_called()


def test_save_user_card_rejects_expired_token(authenticated_event, save_client):
    old = NOW - summon_token.TOKEN_TTL_SECONDS
    ret = save(authenticated_event, summon_body(now=old))

    assert ret["statusCode"] == 410
    save_client.transact_write_items.assert_not_called()


def test_save_user_card_rejects_reused_token(authenticated_event, save_client):
    save_client.transact_write_items.side_effect = transaction_conflict(1)

    ret = save(authenticated_event, summon_body())

    assert ret["statusCode"] == 409


def test_save_user_card_rejects_during_cooldown(authenticated_event, save_client):
    save_client.transact_write_items.side_effect = transaction_conflict(0)
    save_client.get_item.return_value = {"Item": {"lastSummonAt": {"N": "9000"}}}

    ret = save(authenticated_event, summon_body())
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 429
    assert ret["headers"]["Retry-After"] == "2600"
    assert data["retryAfterSeconds"] == 2600


def test_save_user_card_handles_dynamodb_error(authenticated_event, save_client):
    save_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = save(authenticated_event, summon_body())

    assert ret["statusCode"] == 500
