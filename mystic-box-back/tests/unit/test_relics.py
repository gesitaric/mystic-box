import json
import random

import pytest
from mystic_shared import battle, campaign, relics, rules, stats
from mystic_shared.cards import get_character
from mystic_shared.lore import REGIONS, region_of

from relics import app as relics_app
from tests.unit.fake_dynamo import FakeDynamo

USER = "user-123"
HRIMVALD_RELIC = "frostgate-pennant"
# Boreas é de Hrimvald (sintonia com a relíquia de lá); Rowan é de Sylvaran.
ATTUNED, OTHER = "boreas.jfif", "rowan.jfif"


# --------------------------------------------------------------- catálogo ---


def test_every_campaign_region_has_one_relic():
    regions = [relic["region"] for relic in relics.RELICS.values()]
    assert sorted(regions) == sorted(campaign.CAMPAIGN)
    assert len(set(regions)) == len(regions)
    for region_id in campaign.CAMPAIGN:
        assert relics.relic_for_region(region_id)


def test_relics_always_trade_something():
    valid_regions = {region["id"] for region in REGIONS}
    for relic in relics.RELICS.values():
        assert relic["region"] in valid_regions
        assert relic["bonuses"] and relic["penalties"]
        assert set(relic["bonuses"]) | set(relic["penalties"]) <= set(stats.STAT_KEYS)
        assert not set(relic["bonuses"]) & set(relic["penalties"])
        assert all(value > 0 for value in relic["bonuses"].values())
        assert all(value > 0 for value in relic["penalties"].values())
        kind = relic["awakening"][0]
        assert kind in ("status", "aether")
        if kind == "status":
            assert relic["awakening"][1] in battle.STATUSES
            assert battle.STATUSES[relic["awakening"][1]]["kind"] == "buff"
        assert relic["awakeningText"]


def test_attunement_boosts_only_the_bonuses():
    assert region_of(ATTUNED) == "hrimvald" and region_of(OTHER) != "hrimvald"
    plain = relics.stat_changes(HRIMVALD_RELIC, OTHER)
    attuned = relics.stat_changes(HRIMVALD_RELIC, ATTUNED)
    relic = relics.RELICS[HRIMVALD_RELIC]
    for stat, value in relic["bonuses"].items():
        assert plain[stat] == pytest.approx(value)
        assert attuned[stat] == pytest.approx(value * relics.ATTUNED_BONUS_MULTIPLIER)
    for stat, value in relic["penalties"].items():
        assert plain[stat] == attuned[stat] == pytest.approx(-value)
    assert relics.awakening(HRIMVALD_RELIC, OTHER) is None
    assert relics.awakening(HRIMVALD_RELIC, ATTUNED) == relic["awakening"]


def test_relic_changes_battle_stats():
    character = get_character(OTHER)
    base = stats.battle_stats(character)
    equipped = stats.battle_stats(character, relic=HRIMVALD_RELIC)
    assert equipped["bulwark"] > base["bulwark"]
    assert equipped["resolve"] > base["resolve"]
    assert equipped["celerity"] < base["celerity"]
    assert equipped["might"] == base["might"]
    # Relíquia desconhecida não muda nada.
    assert stats.battle_stats(character, relic="nope") == base


def test_unknown_relic_ids_are_ignored():
    assert relics.get_relic(None) is None
    assert relics.get_relic(123) is None
    assert relics.public_equipped("nope", OTHER) is None


# ---------------------------------------------------------------- batalha ---


def team(*names):
    return [get_character(name) for name in names]


def test_attuned_relic_awakens_at_the_start():
    state, events = battle.create_battle(
        "b1", team(ATTUNED, "rowan.jfif", "brina.jfif"), 5, "novice", random.Random(1),
        enemy_team=team("maelis.jfif", "tobin.jfif", "kael.jfif"),
        relics={ATTUNED: HRIMVALD_RELIC, "rowan.jfif": HRIMVALD_RELIC},
    )
    boreas = next(u for u in state["units"] if u["fileName"] == ATTUNED)
    rowan = next(u for u in state["units"] if u["fileName"] == "rowan.jfif")
    brina = next(u for u in state["units"] if u["fileName"] == "brina.jfif")

    relic_events = [e for e in events if e["type"] == "relic"]
    assert [e["target"] for e in relic_events] == [boreas["id"]]
    # O escudo entra logo depois do despertar (os inimigos podem gastá-lo antes
    # da vez do jogador).
    after = events[events.index(relic_events[0]) + 1]
    assert after == {"type": "status", "target": boreas["id"], "status": "shield",
                     "turns": after["turns"]}
    assert not any(e["type"] == "status" and e["target"] == rowan["id"]
                   and e["status"] == "shield" for e in events)

    public = {u["id"]: u for u in battle.public_state(state)["units"]}
    assert public[boreas["id"]]["relic"] == {
        "id": HRIMVALD_RELIC, "name": relics.RELICS[HRIMVALD_RELIC]["name"], "attuned": True,
    }
    assert public[rowan["id"]]["relic"]["attuned"] is False
    assert public[brina["id"]]["relic"] is None


def test_aether_awakening_adds_team_aether():
    # Brina é de Cogsreach: o Overclocked Coil desperta +1 Aether.
    assert region_of("brina.jfif") == "cogsreach"
    _, plain_events = battle.create_battle(
        "b1", team("brina.jfif", "rowan.jfif", "maelis.jfif"), 5, "novice", random.Random(3),
        enemy_team=team("tobin.jfif", "kael.jfif", "jory.jfif"),
    )
    state, events = battle.create_battle(
        "b2", team("brina.jfif", "rowan.jfif", "maelis.jfif"), 5, "novice", random.Random(3),
        enemy_team=team("tobin.jfif", "kael.jfif", "jory.jfif"),
        relics={"brina.jfif": "overclocked-coil"},
    )
    assert any(e["type"] == "relic" for e in events)
    assert not any(e["type"] == "relic" for e in plain_events)


def test_pvp_uses_each_players_relics():
    state, _ = battle.create_pvp_battle(
        "d1", team(ATTUNED, "rowan.jfif", "brina.jfif"), 5,
        team("maelis.jfif", "tobin.jfif", "kael.jfif"), 5, random.Random(1),
        challenger_relics={ATTUNED: HRIMVALD_RELIC},
        opponent_relics={"maelis.jfif": "hearthstone-charm"},
    )
    by_name = {u["fileName"]: u for u in state["units"]}
    assert by_name[ATTUNED]["relic"] == HRIMVALD_RELIC
    assert by_name["maelis.jfif"]["relic"] == "hearthstone-charm"
    assert by_name["rowan.jfif"]["relic"] is None


def test_rules_explain_relics():
    data = rules.public_rules(60, 1800)["relics"]
    assert data["forgeCost"] == relics.FORGE_COST
    assert data["maxCopies"] == relics.MAX_COPIES
    assert len(data["relics"]) == len(relics.RELICS)


# ----------------------------------------------------------------- Lambda ---


TABLES = {
    "cards": ("userId", "ownedCardId"),
    "user_relics": ("userId", "relicId"),
    "card_relics": ("userId", "file_name"),
    "regions": ("userId", None),
    "wallet": ("userId", None),
}


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo(TABLES)
    for index, name in enumerate((ATTUNED, OTHER)):
        fake.tables["cards"][(USER, f"c{index}")] = {
            "userId": {"S": USER}, "ownedCardId": {"S": f"c{index}"}, "file_name": {"S": name},
        }
    monkeypatch.setattr(relics_app, "_client", fake)
    for name, value in {
        "USER_CARDS_TABLE": "cards",
        "USER_RELICS_TABLE": "user_relics",
        "CARD_RELICS_TABLE": "card_relics",
        "REGION_PROGRESS_TABLE": "regions",
        "USER_WALLET_TABLE": "wallet",
    }.items():
        monkeypatch.setattr(relics_app, name, value)
    return fake


def set_balance(db, balance):
    db.tables["wallet"][(USER, None)] = {"userId": {"S": USER}, "balance": {"N": str(balance)}}


def beat_boss(db, region="hrimvald"):
    db.tables["regions"][(USER, None)] = {
        "userId": {"S": USER},
        campaign.stage_attribute(region): {"N": str(campaign.STAGES_PER_REGION)},
    }


def give(db, relic_id, owned, equipped=0):
    db.tables["user_relics"][(USER, relic_id)] = {
        "userId": {"S": USER}, "relicId": {"S": relic_id},
        "owned": {"N": str(owned)}, "equipped": {"N": str(equipped)},
    }


def call(authenticated_event, method, resource, body=None):
    event = authenticated_event(
        httpMethod=method, resource=resource,
        body=json.dumps(body) if body is not None else None,
    )
    ret = relics_app.lambda_handler(event, "")
    return ret["statusCode"], json.loads(ret["body"])


def entry(data, relic_id):
    return next(r for r in data["relics"] if r["id"] == relic_id)


def test_list_shows_every_relic(authenticated_event, db):
    status, data = call(authenticated_event, "GET", "/users/me/relics")
    assert status == 200
    assert len(data["relics"]) == len(relics.RELICS)
    pennant = entry(data, HRIMVALD_RELIC)
    assert pennant["owned"] == 0 and pennant["unlocked"] is False
    assert pennant["canForge"] is False


def test_forge_needs_the_boss(authenticated_event, db):
    set_balance(db, 1000)
    status, data = call(authenticated_event, "POST", "/users/me/relics/forge",
                        {"relicId": HRIMVALD_RELIC})
    assert status == 409
    assert "boss" in data["message"]
    assert db.tables["wallet"][(USER, None)]["balance"]["N"] == "1000"


def test_forge_charges_and_adds_a_copy(authenticated_event, db):
    set_balance(db, relics.FORGE_COST + 10)
    beat_boss(db)
    status, data = call(authenticated_event, "POST", "/users/me/relics/forge",
                        {"relicId": HRIMVALD_RELIC})
    assert status == 200
    assert data["forged"] == HRIMVALD_RELIC
    assert data["balance"] == 10
    assert entry(data, HRIMVALD_RELIC)["owned"] == 1
    assert entry(data, HRIMVALD_RELIC)["free"] == 1


def test_forge_needs_the_shards(authenticated_event, db):
    set_balance(db, relics.FORGE_COST - 1)
    beat_boss(db)
    status, data = call(authenticated_event, "POST", "/users/me/relics/forge",
                        {"relicId": HRIMVALD_RELIC})
    assert status == 409
    assert "Shards" in data["message"]


def test_forge_stops_at_the_max(authenticated_event, db):
    set_balance(db, 10_000)
    beat_boss(db)
    give(db, HRIMVALD_RELIC, relics.MAX_COPIES)
    status, _ = call(authenticated_event, "POST", "/users/me/relics/forge",
                     {"relicId": HRIMVALD_RELIC})
    assert status == 409
    assert db.tables["wallet"][(USER, None)]["balance"]["N"] == "10000"


def test_forge_rejects_unknown_relics(authenticated_event, db):
    status, _ = call(authenticated_event, "POST", "/users/me/relics/forge", {"relicId": "x"})
    assert status == 404


def test_equip_uses_a_free_copy(authenticated_event, db):
    give(db, HRIMVALD_RELIC, 1)
    status, data = call(authenticated_event, "POST", "/users/me/relics/equip",
                        {"fileName": ATTUNED, "relicId": HRIMVALD_RELIC})
    assert status == 200
    assert data["card"]["relic"]["attuned"] is True
    assert entry(data, HRIMVALD_RELIC)["free"] == 0
    assert entry(data, HRIMVALD_RELIC)["equippedOn"][0]["fileName"] == ATTUNED

    # Só tem uma cópia: não dá para equipar em outra personagem.
    status, data = call(authenticated_event, "POST", "/users/me/relics/equip",
                        {"fileName": OTHER, "relicId": HRIMVALD_RELIC})
    assert status == 409
    assert "No free copy" in data["message"]


def test_equip_without_copies_fails(authenticated_event, db):
    status, _ = call(authenticated_event, "POST", "/users/me/relics/equip",
                     {"fileName": ATTUNED, "relicId": HRIMVALD_RELIC})
    assert status == 409
    assert (USER, ATTUNED) not in db.tables["card_relics"]


def test_swap_and_unequip_release_the_copy(authenticated_event, db):
    give(db, HRIMVALD_RELIC, 1)
    give(db, "hearthstone-charm", 1)
    call(authenticated_event, "POST", "/users/me/relics/equip",
         {"fileName": ATTUNED, "relicId": HRIMVALD_RELIC})

    status, data = call(authenticated_event, "POST", "/users/me/relics/equip",
                        {"fileName": ATTUNED, "relicId": "hearthstone-charm"})
    assert status == 200
    assert entry(data, HRIMVALD_RELIC)["free"] == 1
    assert entry(data, "hearthstone-charm")["free"] == 0

    status, data = call(authenticated_event, "POST", "/users/me/relics/equip",
                        {"fileName": ATTUNED, "relicId": None})
    assert status == 200
    assert data["card"]["relic"] is None
    assert entry(data, "hearthstone-charm")["free"] == 1
    assert (USER, ATTUNED) not in db.tables["card_relics"]


def test_equip_needs_the_card(authenticated_event, db):
    give(db, HRIMVALD_RELIC, 1)
    status, _ = call(authenticated_event, "POST", "/users/me/relics/equip",
                     {"fileName": "malachar.jfif", "relicId": HRIMVALD_RELIC})
    assert status == 409


def test_relics_need_login(apigw_event):
    ret = relics_app.lambda_handler(dict(apigw_event, resource="/users/me/relics"), "")
    assert ret["statusCode"] == 401


def test_list_for_a_card_shows_the_effect_on_it(authenticated_event, db, apigw_event):
    give(db, HRIMVALD_RELIC, 1)
    call(authenticated_event, "POST", "/users/me/relics/equip",
         {"fileName": ATTUNED, "relicId": HRIMVALD_RELIC})
    event = authenticated_event(httpMethod="GET", resource="/users/me/relics",
                                queryStringParameters={"fileName": ATTUNED})
    data = json.loads(relics_app.lambda_handler(event, "")["body"])
    assert data["equipped"] == HRIMVALD_RELIC
    assert entry(data, HRIMVALD_RELIC)["forCard"] == relics.public_equipped(
        HRIMVALD_RELIC, ATTUNED
    )
    assert entry(data, "drowned-bell")["forCard"]["attuned"] is False
