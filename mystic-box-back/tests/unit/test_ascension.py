import json

import pytest
from mystic_shared import ascension, battle, cards, rules

from ascend_card import app as ascend_card
from tests.unit.fake_dynamo import FakeDynamo

USER = "user-123"
TABLES = {
    "cards": ("userId", "ownedCardId"),
    "ascensions": ("userId", "file_name"),
}


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo(TABLES)
    monkeypatch.setattr(ascend_card, "_client", fake)
    monkeypatch.setattr(ascend_card, "USER_CARDS_TABLE", "cards")
    monkeypatch.setattr(ascend_card, "CARD_ASCENSIONS_TABLE", "ascensions")
    return fake


def give(db, file_name, count, user=USER):
    for index in range(count):
        owned_id = f"{file_name}-{index}"
        db.tables["cards"][(user, owned_id)] = {
            "userId": {"S": user},
            "ownedCardId": {"S": owned_id},
            "file_name": {"S": file_name},
            "obtainedAt": {"S": f"2026-01-{index + 1:02d}T00:00:00+00:00"},
        }


def owned_ids(db, file_name):
    return sorted(
        item["ownedCardId"]["S"]
        for item in db.tables["cards"].values()
        if item["file_name"]["S"] == file_name
    )


def stored_ascension(db, file_name):
    item = db.tables["ascensions"].get((USER, file_name))
    return int(item["ascension"]["N"]) if item else 0


def ascend(authenticated_event, body):
    event = authenticated_event(
        httpMethod="POST", resource="/users/me/cards/ascend", body=json.dumps(body)
    )
    ret = ascend_card.lambda_handler(event, "")
    return ret["statusCode"], json.loads(ret["body"])


# ---------- regras ----------


def test_costs_cover_every_level():
    assert sorted(ascension.ASCENSION_COSTS) == list(range(1, ascension.MAX_ASCENSION + 1))
    assert ascension.next_ascension_cost(ascension.MAX_ASCENSION) is None


def test_one_copy_always_stays():
    cost = ascension.next_ascension_cost(0)
    assert not ascension.can_ascend(0, cost)
    assert ascension.can_ascend(0, cost + 1)


def test_max_ascension_unlocks_one_more_skill_up_to_supreme():
    rowan = cards.get_character("rowan.jfif")  # 3★
    cassius = cards.get_character("cassius.png")  # 4★
    leoric = cards.get_character("leoric.jfif")  # 5★
    top = ascension.MAX_ASCENSION

    assert len(battle.skills_for(rowan, top)) == len(battle.skills_for(rowan)) + 1
    assert battle.skills_for(cassius, top)[-1] == "unbreakable_oath"
    assert battle.skills_for(leoric, top) == battle.skills_for(leoric)
    assert battle.ascension_unlocks_skill(rowan)
    assert not battle.ascension_unlocks_skill(leoric)
    # Abaixo do máximo, nenhuma habilidade nova.
    assert battle.skills_for(rowan, top - 1) == battle.skills_for(rowan)


def test_ascension_raises_big_stats():
    astra = cards.get_character("astra.jfif")
    base = battle.build_unit(astra, "player", 0, 1)
    ascended = battle.build_unit(astra, "player", 0, 1, ascension=2)

    assert ascended["ascension"] == 2
    assert ascended["stats"]["vitality"] > base["stats"]["vitality"]
    assert ascended["stats"]["celerity"] == base["stats"]["celerity"]


def test_rules_explain_ascension():
    data = rules.public_rules(3600, 1800)["ascension"]

    assert data["maxLevel"] == ascension.MAX_ASCENSION
    assert [level["copies"] for level in data["levels"]] == [
        ascension.ASCENSION_COSTS[level] for level in sorted(ascension.ASCENSION_COSTS)
    ]
    by_rarity = {row["rarity"]: row for row in data["skillsByRarity"]}
    assert by_rarity[3]["ascended"] == by_rarity[3]["base"] + 1
    assert by_rarity[5]["ascended"] == by_rarity[5]["base"]


# ---------- Lambda ----------


def test_options(apigw_event):
    ret = ascend_card.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")
    assert ret["statusCode"] == 200


def test_requires_authentication(apigw_event):
    ret = ascend_card.lambda_handler(dict(apigw_event, httpMethod="POST"), "")
    assert ret["statusCode"] == 401


@pytest.mark.parametrize("body", [{}, {"fileName": 3}, {"fileName": ""}, ["rowan.jfif"]])
def test_rejects_invalid_requests(authenticated_event, db, body):
    status, _ = ascend(authenticated_event, body)
    assert status == 400


def test_unknown_card(authenticated_event, db):
    status, _ = ascend(authenticated_event, {"fileName": "nope.jfif"})
    assert status == 409


def test_card_not_owned(authenticated_event, db):
    status, _ = ascend(authenticated_event, {"fileName": "rowan.jfif"})
    assert status == 404


def test_needs_extra_copies(authenticated_event, db):
    give(db, "rowan.jfif", 1)

    status, data = ascend(authenticated_event, {"fileName": "rowan.jfif"})

    assert status == 409
    assert data["required"] == 2
    assert owned_ids(db, "rowan.jfif") == ["rowan.jfif-0"]
    assert stored_ascension(db, "rowan.jfif") == 0


def test_ascend_consumes_newest_copies_and_keeps_oldest(authenticated_event, db):
    give(db, "rowan.jfif", 3)

    status, data = ascend(authenticated_event, {"fileName": "rowan.jfif", "cost": 0})

    assert status == 200
    assert data["consumed"] == 1
    assert data["quantity"] == 2
    assert data["ascension"]["level"] == 1
    assert owned_ids(db, "rowan.jfif") == ["rowan.jfif-0", "rowan.jfif-1"]
    assert stored_ascension(db, "rowan.jfif") == 1


def test_ascend_to_max_then_stop(authenticated_event, db):
    total = sum(ascension.ASCENSION_COSTS.values()) + 1
    give(db, "rowan.jfif", total)

    for level in range(1, ascension.MAX_ASCENSION + 1):
        status, data = ascend(authenticated_event, {"fileName": "rowan.jfif"})
        assert status == 200
        assert data["ascension"]["level"] == level

    assert owned_ids(db, "rowan.jfif") == ["rowan.jfif-0"]
    assert data["battle"]["skills"][-1]["id"] == "tremor_slam"

    give(db, "rowan.jfif", 5)
    status, _ = ascend(authenticated_event, {"fileName": "rowan.jfif"})
    assert status == 409
    assert stored_ascension(db, "rowan.jfif") == ascension.MAX_ASCENSION


def test_concurrent_ascension_consumes_nothing(authenticated_event, db, monkeypatch):
    give(db, "rowan.jfif", 3)
    # Outra requisição subiu a ascensão depois da leitura.
    db.tables["ascensions"][(USER, "rowan.jfif")] = {
        "userId": {"S": USER},
        "file_name": {"S": "rowan.jfif"},
        "ascension": {"N": "1"},
    }
    monkeypatch.setattr(ascend_card, "get_ascension", lambda user_id, file_name: (0, False))

    status, _ = ascend(authenticated_event, {"fileName": "rowan.jfif"})

    assert status == 409
    assert len(owned_ids(db, "rowan.jfif")) == 3
    assert stored_ascension(db, "rowan.jfif") == 1


def test_kept_copy_must_still_be_owned(authenticated_event, db, monkeypatch):
    give(db, "rowan.jfif", 1)
    # A cópia que ficaria foi anunciada no mercado ao mesmo tempo.
    monkeypatch.setattr(
        ascend_card,
        "get_owned_copies",
        lambda user_id, file_name: [
            {"ownedCardId": "rowan.jfif-0", "obtainedAt": "b"},
            {"ownedCardId": "listed-copy", "obtainedAt": "a"},
        ],
    )

    status, _ = ascend(authenticated_event, {"fileName": "rowan.jfif"})

    assert status == 409
    assert owned_ids(db, "rowan.jfif") == ["rowan.jfif-0"]
    assert stored_ascension(db, "rowan.jfif") == 0
