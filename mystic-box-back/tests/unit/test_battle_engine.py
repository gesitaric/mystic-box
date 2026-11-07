import json
import random

import pytest
from mystic_shared import battle, cards


def team(*file_names):
    return [cards.get_character(name) for name in file_names]


PLAYER = ("rowan.jfif", "brina.jfif", "maelis.jfif")
FOES = ("tobin.jfif", "kael.jfif", "corvus.jfif")


def new_battle(seed=1, player=PLAYER, foes=FOES, level=1, difficulty="novice"):
    return battle.create_battle(
        "battle-1", team(*player), level, difficulty, random.Random(seed),
        enemy_team=team(*foes),
    )


def unit(state, unit_id):
    return next(u for u in state["units"] if u["id"] == unit_id)


def play_until_end(state, seed=2, max_turns=500):
    rng = random.Random(seed)
    for _ in range(max_turns):
        if state["status"] != "active":
            return
        battle.play_turn(state, {"type": "auto"}, rng)
    raise AssertionError("Battle never ended")


class FixedRng:
    """Sem variação e sem crítico."""

    def uniform(self, a, b):
        return 1.0

    def random(self):
        return 0.999


# ---------- habilidades ----------


def test_every_archetype_has_three_skills_defined():
    for skills in battle.ARCHETYPE_SKILLS.values():
        assert len(skills) == 3
        for skill_id in skills:
            assert battle.SKILLS[skill_id]["target"] in battle.TARGET_TYPES


def test_rarity_unlocks_skills():
    assert battle.skills_for(cards.get_character("rowan.jfif")) == [
        "strike", "guard", "bastion_call"
    ]
    assert len(battle.skills_for(cards.get_character("cassius.png"))) == 4
    assert battle.skills_for(cards.get_character("leoric.jfif"))[-1] == "unbreakable_oath"


# ---------- montagem ----------


def test_create_battle_waits_for_a_player_turn():
    state, events = new_battle()

    assert state["status"] == "active"
    assert unit(state, state["turn"])["side"] == "player"
    assert events[0]["type"] == "round"
    assert [u["id"] for u in state["units"]] == ["p0", "p1", "p2", "e0", "e1", "e2"]
    json.dumps(state)  # precisa ser guardado como JSON


def test_create_battle_validates_team():
    with pytest.raises(battle.BattleError):
        battle.create_battle("b", team("rowan.jfif", "brina.jfif"), 1, "novice", random.Random())
    with pytest.raises(battle.BattleError):
        battle.create_battle(
            "b", team("rowan.jfif", "rowan.jfif", "brina.jfif"), 1, "novice", random.Random()
        )
    with pytest.raises(battle.BattleError):
        battle.create_battle("b", team(*PLAYER), 1, "legendary", random.Random())


def test_difficulty_requires_level():
    with pytest.raises(battle.BattleError, match="level"):
        battle.create_battle("b", team(*PLAYER), 1, "master", random.Random())
    state, _ = battle.create_battle("b", team(*PLAYER), 6, "master", random.Random(3))
    assert state["enemyLevel"] == 8


def test_enemy_level_follows_difficulty():
    assert battle.enemy_level(1, "novice") == 1
    assert battle.enemy_level(10, "novice") == 8
    assert battle.enemy_level(10, "adept") == 10


def test_draw_enemy_team_is_distinct():
    rng = random.Random(5)
    for _ in range(200):
        foes = battle.draw_enemy_team("master", rng)
        assert len({c["file_name"] for c in foes}) == battle.TEAM_SIZE


def test_public_difficulties():
    options = {d["id"]: d for d in battle.public_difficulties(3)}
    assert options["novice"]["unlocked"] and options["adept"]["unlocked"]
    assert not options["master"]["unlocked"]


# ---------- turnos ----------


def test_player_can_strike_an_enemy():
    state, _ = new_battle()
    actor = state["turn"]
    hp_before = unit(state, "e0")["hp"]

    events = battle.play_turn(
        state, {"type": "skill", "skill": "strike", "target": "e0"}, random.Random(9)
    )

    assert events[0]["type"] == "skill" and events[0]["actor"] == actor
    damage = next(e for e in events if e["type"] == "damage")
    assert damage["target"] == "e0"
    assert damage["hp"] < hp_before


def test_skill_costs_aether():
    state, _ = new_battle()
    state["aether"]["player"] = 3
    actor = unit(state, state["turn"])
    skill_id = actor["skills"][2]
    target = battle.valid_targets(state, actor, skill_id)[0]

    events = battle.play_turn(
        state, {"type": "skill", "skill": skill_id, "target": target}, random.Random(1)
    )

    assert events[0]["aether"]["player"] == 0


def test_cannot_use_skill_without_aether():
    state, _ = new_battle()
    state["aether"]["player"] = 0
    actor = unit(state, state["turn"])

    with pytest.raises(battle.BattleError, match="Aether"):
        battle.play_turn(state, {"type": "skill", "skill": actor["skills"][2]}, random.Random())


def test_cannot_use_unknown_or_foreign_skill():
    state, _ = new_battle()
    with pytest.raises(battle.BattleError):
        battle.play_turn(state, {"type": "skill", "skill": "nuke"}, random.Random())
    with pytest.raises(battle.BattleError):
        battle.play_turn(state, {"type": "skill", "skill": "rebirth_hymn"}, random.Random())


def test_cannot_target_ally_with_attack():
    state, _ = new_battle()
    with pytest.raises(battle.BattleError, match="target"):
        battle.play_turn(
            state, {"type": "skill", "skill": "strike", "target": "p1"}, random.Random()
        )


def test_taunt_forces_target():
    state, _ = new_battle()
    unit(state, "e1")["statuses"]["taunt"] = {"turns": 2}

    with pytest.raises(battle.BattleError, match="taunting"):
        battle.play_turn(
            state, {"type": "skill", "skill": "strike", "target": "e0"}, random.Random()
        )
    actor = unit(state, state["turn"])
    assert battle.valid_targets(state, actor, "strike") == ["e1"]


def test_guard_halves_damage():
    attacker = battle.build_unit(cards.get_character("kael.jfif"), "enemy", 0, 1)
    defender = battle.build_unit(cards.get_character("rowan.jfif"), "player", 0, 1)
    guarded = json.loads(json.dumps(defender))
    guarded["statuses"]["guard"] = {"turns": 1}

    normal = battle._deal_damage(attacker, defender, 1.0, "physical", FixedRng(), [])
    reduced = battle._deal_damage(attacker, guarded, 1.0, "physical", FixedRng(), [])

    assert reduced == pytest.approx(normal / 2, abs=1)


def test_shield_absorbs_damage():
    attacker = battle.build_unit(cards.get_character("kael.jfif"), "enemy", 0, 1)
    defender = battle.build_unit(cards.get_character("rowan.jfif"), "player", 0, 1)
    defender["statuses"]["shield"] = {"turns": 2, "value": 1000}
    events = []

    battle._deal_damage(attacker, defender, 1.0, "physical", FixedRng(), events)

    assert defender["hp"] == defender["maxHp"]
    assert events[0]["amount"] == 0 and events[0]["absorbed"] > 0


def test_element_advantage_increases_damage():
    ember = battle.build_unit(cards.get_character("kael.jfif"), "enemy", 0, 1)
    gale = battle.build_unit(cards.get_character("jory.jfif"), "player", 0, 1)
    tide = battle.build_unit(cards.get_character("brina.jfif"), "player", 1, 1)
    # Mesma defesa para comparar só o elemento.
    tide["stats"] = dict(gale["stats"])
    events = []

    strong = battle._deal_damage(ember, gale, 1.0, "physical", FixedRng(), events)
    weak = battle._deal_damage(ember, tide, 1.0, "physical", FixedRng(), events)

    assert events[0]["effectiveness"] == "strong"
    assert events[1]["effectiveness"] == "weak"
    assert strong > weak


def test_stun_skips_turn():
    state, _ = new_battle()
    actor = unit(state, state["turn"])
    events = []
    actor["statuses"]["stun"] = {"turns": 1}

    assert battle._start_turn(state, actor, events) is False
    assert any(e["type"] == "stunned" for e in events)
    assert "stun" not in actor["statuses"]


def test_burn_ticks_and_expires():
    state, _ = new_battle()
    actor = unit(state, state["turn"])
    actor["statuses"]["burn"] = {"turns": 2}
    for _ in range(2):
        events = []
        battle._start_turn(state, actor, events)
        battle._end_turn(state, actor)
        assert any(e.get("status") == "burn" for e in events)
    assert "burn" not in actor["statuses"]


def test_self_buff_lasts_through_enemy_turns():
    state, _ = new_battle()
    actor = unit(state, state["turn"])
    state["acting"] = actor["id"]
    battle._apply_status(state, actor, "taunt", 2, [])
    battle._end_turn(state, actor)

    # Ainda provoca durante a próxima rodada inteira.
    assert actor["statuses"]["taunt"]["turns"] == 2


def test_rebirth_hymn_revives_fallen_ally():
    state, _ = new_battle(player=("seraphiel.jfif", "rowan.jfif", "brina.jfif"))
    state["turn"] = "p0"
    state["aether"]["player"] = 10
    unit(state, "p1")["hp"] = 0

    battle.play_turn(
        state, {"type": "skill", "skill": "rebirth_hymn", "target": "p1"}, random.Random(4)
    )

    assert unit(state, "p1")["hp"] > 0 or state["status"] != "active"


def test_aether_siphon_steals_aether():
    state, _ = new_battle(player=("lyra.png", "rowan.jfif", "brina.jfif"))
    state["aether"] = {"player": 5, "enemy": 4}
    events = []

    battle._perform(state, unit(state, "p0"), "aether_siphon", None, random.Random(1), events)

    steal = next(e for e in events if e["type"] == "aether")
    assert steal["amount"] == 2
    assert state["aether"] == {"player": 2, "enemy": 2}


def test_call_companion_summons_monster_that_strikes_each_turn():
    state, _ = new_battle(player=("liesel.jfif", "rowan.jfif", "brina.jfif"))
    summoner = unit(state, "p0")
    summoner["hp"] = summoner["maxHp"]
    state["aether"]["player"] = 5
    state["acting"] = "p0"
    events = []

    battle._perform(state, summoner, "call_companion", "e0", random.Random(1), events)
    battle._end_turn(state, summoner)

    assert summoner["statuses"]["companion"]["turns"] == battle.COMPANION_TURNS
    strikes = 0
    for _ in range(battle.COMPANION_TURNS):
        events = []
        battle._start_turn(state, summoner, events, random.Random(2))
        battle._end_turn(state, summoner)
        strikes += sum(1 for e in events if e["type"] == "damage" and e.get("companion"))
    assert strikes == battle.COMPANION_TURNS
    assert "companion" not in summoner["statuses"]


def test_companion_respects_taunt():
    state, _ = new_battle(player=("liesel.jfif", "rowan.jfif", "brina.jfif"))
    summoner = unit(state, "p0")
    summoner["statuses"]["companion"] = {"turns": 2}
    unit(state, "e1")["statuses"]["taunt"] = {"turns": 2}
    events = []

    battle._start_turn(state, summoner, events, random.Random(3))

    hit = next(e for e in events if e["type"] == "damage" and e.get("companion"))
    assert hit["target"] == "e1"


def test_beast_rampage_exposes_only_with_companion():
    state, _ = new_battle(player=("grizelda.jfif", "rowan.jfif", "brina.jfif"))
    summoner = unit(state, "p0")
    state["aether"]["player"] = 10
    events = []
    battle._perform(state, summoner, "beast_rampage", None, random.Random(1), events)
    assert not any(e["type"] == "status" and e["status"] == "expose" for e in events)

    summoner["statuses"]["companion"] = {"turns": 2}
    events = []
    battle._perform(state, summoner, "beast_rampage", None, random.Random(1), events)
    assert any(e["type"] == "status" and e["status"] == "expose" for e in events)


def test_volt_bolt_chains_to_another_foe():
    state, _ = new_battle(player=("ophira.jfif", "rowan.jfif", "brina.jfif"))
    state["aether"]["player"] = 5
    events = []

    battle._perform(state, unit(state, "p0"), "elemental_bolt", "e0", FixedRng(), events)

    chained = [e for e in events if e["type"] == "damage" and e.get("chain")]
    assert len(chained) == 1
    assert chained[0]["target"] != "e0"


def test_terra_beats_volt_and_volt_beats_tide():
    from mystic_shared import stats

    assert stats.element_multiplier("terra", "volt") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("volt", "tide") == stats.ADVANTAGE_MULTIPLIER
    assert stats.element_multiplier("volt", "terra") == stats.DISADVANTAGE_MULTIPLIER


# ---------- fim e recompensa ----------


def test_forfeit_ends_without_experience():
    state, _ = new_battle()
    events = battle.play_turn(state, {"type": "forfeit"}, random.Random())

    assert state["status"] == "lost"
    assert events[-1] == {"type": "end", "result": "lost", "reason": "forfeit"}
    assert battle.battle_experience(state) == 0


def test_cannot_act_after_battle_ends():
    state, _ = new_battle()
    battle.play_turn(state, {"type": "forfeit"}, random.Random())
    with pytest.raises(battle.BattleError):
        battle.play_turn(state, {"type": "auto"}, random.Random())


def test_battles_always_end_and_reward_experience():
    win_xp = battle.DIFFICULTIES["novice"]["experience"]
    for seed in range(40):
        state, _ = new_battle(seed=seed)
        play_until_end(state, seed=seed)
        json.dumps(state)
        assert state["status"] in ("won", "lost")
        xp = battle.battle_experience(state)
        if state["status"] == "won":
            assert xp == win_xp
        else:
            assert 0 < xp < win_xp


def test_random_battles_never_break():
    rng = random.Random(77)
    for seed in range(60):
        player = rng.sample(cards.CHARACTERS, 3)
        state, _ = battle.create_battle(
            f"b{seed}", player, 6, rng.choice(["novice", "adept", "master"]),
            random.Random(seed),
        )
        play_until_end(state, seed=seed)


def test_timeout_is_a_loss():
    state, _ = new_battle()
    state["round"] = battle.MAX_ROUNDS
    state["queue"] = []
    battle._advance(state, random.Random(), [])

    assert state["status"] == "lost"
    assert state["endReason"] == "timeout"


def test_public_state_lists_actions_for_current_card():
    state, _ = new_battle()
    view = battle.public_state(state)

    assert view["turn"] == state["turn"]
    assert [a["id"] for a in view["actions"]] == unit(state, state["turn"])["skills"]
    strike = next(a for a in view["actions"] if a["id"] == "strike")
    assert strike["usable"] and set(strike["targets"]) == {"e0", "e1", "e2"}
    assert len(view["units"]) == 6
    json.dumps(view)
