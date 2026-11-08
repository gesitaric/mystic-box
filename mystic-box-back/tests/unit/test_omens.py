import random
from datetime import datetime, timedelta, timezone

from mystic_shared import battle, cards, omens
from mystic_shared.mastery import regions_with_residents


def at(day):
    return datetime.combine(omens.OMEN_EPOCH + timedelta(days=day), datetime.min.time(),
                            timezone.utc)


def test_every_region_with_champions_has_an_omen():
    assert set(omens.OMENS) == set(regions_with_residents())


def test_featured_region_rotates_every_monday():
    regions = regions_with_residents()
    assert omens.current_region(at(0)) == regions[0]
    assert omens.current_region(at(6)) == regions[0]
    assert omens.current_region(at(7)) == regions[1]
    assert omens.current_region(at(7 * len(regions))) == regions[0]


def test_public_omen_says_when_it_ends():
    omen = omens.public_omen(at(3))
    assert omen["endsAt"] == at(7).isoformat()
    assert omen["title"] == omens.OMENS[omen["region"]][0]


def test_featured_cards_are_likelier_without_changing_rarity_odds():
    featured = omens.featured_file_names(at(0))
    weights = cards.card_weights(cards.CHARACTERS, cards.RARITY_WEIGHTS, featured, 3)
    by_name = dict(zip((c["file_name"] for c in cards.CHARACTERS), weights))
    for rarity in (3, 4, 5):
        group = [c for c in cards.CHARACTERS if c["rarity"] == rarity]
        total = sum(by_name[c["file_name"]] for c in group)
        assert abs(total - cards.RARITY_WEIGHTS[rarity] * len(group)) < 1e-6
        boosted = [c for c in group if c["file_name"] in featured]
        plain = [c for c in group if c["file_name"] not in featured]
        if boosted and plain:
            assert by_name[boosted[0]["file_name"]] == 3 * by_name[plain[0]["file_name"]]


def test_omen_boosts_experience_for_a_team_with_a_herald():
    state, _ = battle.create_battle(
        "b", [cards.get_character(n) for n in ("rowan.jfif", "brina.jfif", "maelis.jfif")],
        1, "novice", random.Random(1),
        enemy_team=[cards.get_character(n) for n in ("tobin.jfif", "kael.jfif", "corvus.jfif")],
    )
    events = battle.mark_omen(state, "sylvaran", 0.25, "The Moonbloom")
    assert events[0]["targets"] == ["p0"]
    state["status"], state["endReason"] = "won", "victory"
    base = battle.DIFFICULTIES["novice"]["experience"]
    assert battle.battle_experience(state) == round(base * 1.25)

    assert battle.mark_omen(state, "nocthaven", 0.25, "x") == []
