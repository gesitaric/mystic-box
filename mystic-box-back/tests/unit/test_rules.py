import json

from mystic_shared import battle, cards, progression, rules, stats

from get_rules import app as get_rules


def test_get_rules_options(apigw_event):
    ret = get_rules.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_rules_is_public_and_uses_server_constants(apigw_event):
    ret = get_rules.lambda_handler(dict(apigw_event, httpMethod="GET"), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["summon"]["cardsPerSummon"] == cards.SUMMON_SIZE
    assert data["summon"]["cooldownSeconds"] == get_rules.SUMMON_COOLDOWN_SECONDS
    assert data["shop"]["maxSellQuantity"] == cards.MAX_SELL_QUANTITY
    assert data["progression"]["maxLevel"] == progression.MAX_LEVEL
    assert data["battle"]["teamSize"] == battle.TEAM_SIZE
    assert data["battle"]["aether"]["max"] == battle.MAX_AETHER
    assert {d["id"] for d in data["battle"]["difficulties"]} == set(battle.DIFFICULTIES)
    assert {s["id"] for s in data["battle"]["statuses"]} == set(battle.STATUSES)


def test_rarity_chances_add_up_to_100():
    for weights in (cards.RARITY_WEIGHTS, cards.LAST_CARD_RARITY_WEIGHTS):
        chances = rules.rarity_chances(weights)
        assert abs(sum(c["chance"] for c in chances) - 100) < 0.5
        assert sum(c["cardCount"] for c in chances) == len(cards.CHARACTERS)


def test_last_card_is_luckier():
    normal = {c["rarity"]: c["chance"] for c in rules.rarity_chances(cards.RARITY_WEIGHTS)}
    last = {c["rarity"]: c["chance"] for c in rules.rarity_chances(cards.LAST_CARD_RARITY_WEIGHTS)}
    assert last[5] > normal[5]


def test_archetype_skills_unlock_by_rarity():
    data = rules.public_rules(3600, 1800)["battle"]
    for archetype in data["archetypes"]:
        assert [s["unlockRarity"] for s in archetype["skills"]] == [3, 4, 5]
        assert [s["supreme"] for s in archetype["skills"]] == [False, False, True]
        for skill in archetype["skills"]:
            character = {"rarity": skill["unlockRarity"], "archetype": archetype["id"]}
            assert skill["id"] in battle.skills_for(character)


def test_element_matchups_match_damage_multiplier():
    elements = rules.public_rules(3600, 1800)["battle"]["elements"]
    for element in elements["list"]:
        for other in element["strongAgainst"]:
            assert stats.element_multiplier(element["id"], other) == elements["advantageMultiplier"]
        for other in element["weakAgainst"]:
            assert stats.element_multiplier(element["id"], other) == elements["disadvantageMultiplier"]
