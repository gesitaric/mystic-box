from mystic_shared import cards, stats


def test_every_card_has_a_known_element_and_archetype():
    for character in cards.CHARACTERS:
        assert character["element"] in stats.ELEMENTS
        assert character["archetype"] in stats.ARCHETYPES


def test_every_element_and_archetype_is_used():
    assert {c["element"] for c in cards.CHARACTERS} == set(stats.ELEMENTS)
    assert {c["archetype"] for c in cards.CHARACTERS} == set(stats.ARCHETYPES)


def test_battle_stats_are_positive_integers():
    for character in cards.CHARACTERS:
        values = stats.battle_stats(character)
        assert set(values) == set(stats.STAT_KEYS)
        for value in values.values():
            assert isinstance(value, int) and value > 0
        assert values["fate"] <= stats.MAX_FATE


def test_battle_stats_are_stable():
    astra = cards.get_character("astra.jfif")
    assert stats.battle_stats(astra) == stats.battle_stats(astra)


def test_cards_with_same_archetype_and_rarity_differ():
    vanguards = [
        c for c in cards.CHARACTERS if c["archetype"] == "vanguard" and c["rarity"] == 3
    ]
    assert len(vanguards) >= 2
    first, second = (stats.battle_stats(c) for c in vanguards[:2])
    assert first != second


def test_higher_rarity_is_stronger_on_average():
    def average_total(rarity):
        group = [c for c in cards.CHARACTERS if c["rarity"] == rarity]
        totals = [sum(stats.battle_stats(c).values()) for c in group]
        return sum(totals) / len(totals)

    assert average_total(5) > average_total(4) > average_total(3)


def test_level_increases_stats():
    rowan = cards.get_character("rowan.jfif")
    base = stats.battle_stats(rowan, level=1)
    leveled = stats.battle_stats(rowan, level=10)
    assert leveled["vitality"] > base["vitality"]
    assert leveled["might"] > base["might"]
    # Velocidade e crítico não mudam com o nível.
    assert leveled["celerity"] == base["celerity"]


def test_element_multiplier():
    assert stats.element_multiplier("ember", "gale") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("gale", "ember") == stats.DISADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("tide", "ember") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("lumen", "umbra") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("umbra", "lumen") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("ember", "lumen") == 1.0
    assert stats.element_multiplier("ember", "ember") == 1.0


def test_public_battle_profile():
    profile = stats.public_battle_profile(cards.get_character("ignis.jfif"))
    assert profile["element"] == "ember"
    assert profile["archetype"] == "duelist"
    assert profile["strongAgainst"] == ["gale"]
    assert profile["stats"] == stats.battle_stats(cards.get_character("ignis.jfif"))
