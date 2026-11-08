"""Motor de batalha: contra o computador ou duelo online entre jogadores.

Batalha por turnos entre dois times de 3 cartas. Regras principais:

- Rodadas: no começo de cada rodada todos os combatentes vivos entram numa
  fila ordenada por `celerity` (quem está lento perde velocidade). Cada um age
  uma vez por rodada.
- Aether: recurso compartilhado por time (máx. MAX_AETHER). Cada turno gera
  AETHER_PER_TURN; Strike e Guard geram um pouco mais. Habilidades custam Aether,
  então o jogador decide entre gastar agora ou acumular para algo maior.
- Habilidades: todo combatente tem Strike e Guard; o arquétipo dá mais
  habilidades conforme a raridade (3★ uma, 4★ duas, 5★ três, incluindo a
  suprema).
- Elementos: dano com vantagem elemental x1.3, com desvantagem x0.8. Os
  feitiços dos Arcanistas carregam um efeito do seu elemento.
- Efeitos: queimadura, atordoamento, enfraquecer, expor, lentidão, escudo,
  provocação, regeneração, fortalecer, guarda e companheiro (o monstro dos
  Invocadores, que ataca no começo de cada turno da carta).
- Laços: cartas com laço (`lore.BONDS`) no mesmo time ganham
  BOND_STAT_BONUS nos atributos grandes por parceiro; quando uma cai, os
  parceiros vivos ganham Fortalecer por BOND_GRIEF_TURNS turnos.
- Rivalidades: rivais (`lore.RIVALRIES`) em times opostos causam
  RIVAL_DAMAGE_MULTIPLIER de dano um ao outro.
- Provocação: golpes de alvo único precisam mirar quem está provocando.
- Duelo online (mode "pvp"): as mesmas regras, mas os dois lados são
  jogadores. O lado "player" é quem desafiou e o "enemy" quem aceitou; cada
  um luta no próprio nível, sem bônus de dificuldade. Se as rodadas acabarem,
  é empate. `public_state`/`view_events` mostram a batalha do ponto de vista
  de cada lado (o próprio time sempre aparece como "player").

O estado da batalha é um dict serializável em JSON, guardado pelo servidor. O
cliente só manda a intenção (habilidade e alvo); tudo é validado e calculado
aqui. Funções que sorteiam recebem `rng` (random.Random) para testes
determinísticos.
"""

import random

from .ascension import MAX_ASCENSION, bonus_skills, clamp_ascension
from .cards import CHARACTERS
from .lore import bond_between, rivalry_between
from .progression import MAX_LEVEL
from .stats import ARCHETYPES, ELEMENTS, SCALED_STATS, battle_stats, element_multiplier

TEAM_SIZE = 3
MAX_AETHER = 10
STARTING_AETHER = 2
AETHER_PER_TURN = 1
# Aether extra que Strike e Guard geram (além do AETHER_PER_TURN).
BASIC_SKILL_AETHER = 1
MAX_ROUNDS = 30

DEFENSE_CONSTANT = 50
DAMAGE_VARIANCE = 0.1
CRIT_MULTIPLIER = 1.5
# Dano híbrido: soma Might e Arcana com este peso (contra a média das defesas).
HYBRID_POWER_RATIO = 0.7

BURN_RATIO = 0.07
REGEN_RATIO = 0.08
WEAKEN_MULTIPLIER = 0.75
EXPOSE_MULTIPLIER = 1.25
EMPOWER_MULTIPLIER = 1.3
GUARD_MULTIPLIER = 0.5
SLOW_MULTIPLIER = 0.6

# Monstro companheiro dos Invocadores: golpe híbrido no começo de cada turno.
COMPANION_MULTIPLIER = 0.75
COMPANION_TURNS = 3

# Laços (BONDS de lore.py) no mesmo time: cada parceiro de laço aumenta os
# atributos grandes da carta; quando um parceiro cai, os que ficam ganham
# Fortalecer por alguns turnos.
BOND_STAT_BONUS = 0.06
BOND_GRIEF_TURNS = 2
# Rivalidades (RIVALRIES de lore.py) em times opostos: cada rival causa mais
# dano ao outro.
RIVAL_DAMAGE_MULTIPLIER = 1.2

# Experiência de uma derrota: fração da experiência de vitória + bônus por
# inimigo derrotado. Desistir não dá experiência.
LOSS_EXPERIENCE_RATIO = 0.3
LOSS_EXPERIENCE_PER_DEFEAT = 5

# Duelo online: experiência da vitória (derrota e empate seguem
# LOSS_EXPERIENCE_RATIO/LOSS_EXPERIENCE_PER_DEFEAT; desistir/abandonar dá 0).
PVP = {
    "label": "Online duel",
    "experience": 90,
}

# Motivos de fim em que o perdedor saiu da batalha (não ganha experiência).
WITHDRAW_REASONS = ("forfeit", "abandon")

DIFFICULTIES = {
    "novice": {
        "enemyPower": 0.85,
        "label": "Novice",
        "description": "Weaker foes, mostly common cards.",
        "minLevel": 1,
        "levelOffset": -2,
        "rarityWeights": {3: 70, 4: 25, 5: 5},
        "experience": 40,
    },
    "adept": {
        "enemyPower": 0.9,
        "label": "Adept",
        "description": "Foes of your level with more rare cards.",
        "minLevel": 3,
        "levelOffset": 0,
        "rarityWeights": {3: 40, 4: 45, 5: 15},
        "experience": 70,
    },
    "master": {
        "enemyPower": 1.0,
        "label": "Master",
        "description": "Stronger foes led by legendary cards.",
        "minLevel": 6,
        "levelOffset": 2,
        "rarityWeights": {3: 15, 4: 50, 5: 35},
        "experience": 110,
    },
}

STATUSES = {
    "burn": {"label": "Burn", "kind": "debuff",
             "description": "Loses 7% of max vitality at the start of each turn."},
    "stun": {"label": "Stun", "kind": "debuff", "description": "Skips the next turn."},
    "weaken": {"label": "Weaken", "kind": "debuff", "description": "Deals 25% less damage."},
    "expose": {"label": "Expose", "kind": "debuff", "description": "Takes 25% more damage."},
    "slow": {"label": "Slow", "kind": "debuff",
             "description": "Celerity reduced by 40%: acts later in the round."},
    "shield": {"label": "Shield", "kind": "buff", "description": "Absorbs incoming damage."},
    "taunt": {"label": "Taunt", "kind": "buff",
              "description": "Single-target attacks must aim at this card."},
    "regen": {"label": "Regen", "kind": "buff",
              "description": "Recovers 8% of max vitality at the start of each turn."},
    "empower": {"label": "Empower", "kind": "buff", "description": "Deals 30% more damage."},
    "guard": {"label": "Guard", "kind": "buff",
              "description": "Takes 50% less damage until its next turn."},
    "companion": {"label": "Companion", "kind": "buff",
                  "description": "Its bonded monster strikes a foe (0.75x hybrid) at "
                                 "the start of each of this card's turns."},
}

# Efeito que os feitiços de cada elemento carregam.
ELEMENT_RIDERS = {
    "ember": "Sets the target ablaze (Burn).",
    "tide": "Drenches the target (Slow).",
    "gale": "Tears the target's guard open (Expose).",
    "terra": "Crushes the target's strength (Weaken).",
    "volt": "Lightning arcs to the weakest other foe for 35% of the damage.",
    "lumen": "Heals the most wounded ally for 30% of the damage.",
    "umbra": "Drains 35% of the damage as vitality.",
}

LUMEN_HEAL_RATIO = 0.3
UMBRA_DRAIN_RATIO = 0.35
VOLT_CHAIN_RATIO = 0.35

TARGET_TYPES = ("enemy", "all_enemies", "ally", "all_allies", "self", "fallen_ally")


class BattleError(ValueError):
    """Ação inválida pedida pelo jogador."""


# ------------------------------------------------------------- utilidades ---


def _unit(state, unit_id):
    for unit in state["units"]:
        if unit["id"] == unit_id:
            return unit
    return None


def _alive(unit):
    return unit["hp"] > 0


def _team(state, side, alive=True):
    return [u for u in state["units"] if u["side"] == side and _alive(u) == alive]


def _opponent(side):
    return "enemy" if side == "player" else "player"


def _has(unit, status):
    return status in unit["statuses"]


def _apply_status(state, target, status, turns, events, value=None):
    if not _alive(target):
        return
    # Duração conta turnos do alvo; o turno atual do próprio alvo não conta.
    if state.get("acting") == target["id"]:
        turns += 1
    current = target["statuses"].get(status)
    entry = {"turns": max(turns, current["turns"] if current else 0)}
    if value is not None:
        entry["value"] = max(value, (current or {}).get("value", 0))
    target["statuses"][status] = entry
    events.append({"type": "status", "target": target["id"], "status": status,
                   "turns": entry["turns"]})


def _cleanse(target, events):
    debuffs = [s for s in target["statuses"] if STATUSES[s]["kind"] == "debuff"]
    for status in debuffs:
        del target["statuses"][status]
    if debuffs:
        events.append({"type": "cleanse", "target": target["id"], "statuses": debuffs})


def _gain_aether(state, side, amount):
    state["aether"][side] = min(MAX_AETHER, state["aether"][side] + amount)


def _heal(target, amount, events, source=None, status=None):
    if not _alive(target):
        return 0
    healed = max(0, min(round(amount), target["maxHp"] - target["hp"]))
    target["hp"] += healed
    event = {"type": "heal", "target": target["id"], "amount": healed, "hp": target["hp"]}
    if source:
        event["source"] = source["id"]
    if status:
        event["status"] = status
    events.append(event)
    return healed


def _defeat(target, events):
    target["hp"] = 0
    target["statuses"] = {}
    events.append({"type": "defeated", "target": target["id"]})


def _lose_hp(target, amount, events, event):
    """Aplica dano já calculado, consumindo o escudo primeiro."""
    absorbed = 0
    shield = target["statuses"].get("shield")
    if shield:
        absorbed = min(shield["value"], amount)
        shield["value"] -= absorbed
        if shield["value"] <= 0:
            del target["statuses"]["shield"]
    target["hp"] = max(0, target["hp"] - (amount - absorbed))
    events.append({**event, "target": target["id"], "amount": amount - absorbed,
                   "absorbed": absorbed, "hp": target["hp"]})
    if target["hp"] == 0:
        _defeat(target, events)
    return amount - absorbed


def _deal_damage(attacker, defender, multiplier, kind, rng, events, pierce=0.0, extra=None):
    """Calcula e aplica um golpe. Devolve o dano causado à vitalidade."""
    stats_a, stats_d = attacker["stats"], defender["stats"]
    if kind == "physical":
        power, defense = stats_a["might"], stats_d["bulwark"]
    elif kind == "magical":
        power, defense = stats_a["arcana"], stats_d["resolve"]
    else:  # híbrido
        power = (stats_a["might"] + stats_a["arcana"]) * HYBRID_POWER_RATIO
        defense = (stats_d["bulwark"] + stats_d["resolve"]) / 2

    defense *= 1 - pierce
    damage = power * multiplier * DEFENSE_CONSTANT / (DEFENSE_CONSTANT + defense)

    affinity = element_multiplier(attacker["element"], defender["element"])
    damage *= affinity
    if _has(attacker, "empower"):
        damage *= EMPOWER_MULTIPLIER
    if _has(attacker, "weaken"):
        damage *= WEAKEN_MULTIPLIER
    if _has(defender, "expose"):
        damage *= EXPOSE_MULTIPLIER
    if _has(defender, "guard"):
        damage *= GUARD_MULTIPLIER
    rival = defender["id"] in attacker.get("rivals", ())
    if rival:
        damage *= RIVAL_DAMAGE_MULTIPLIER

    damage *= rng.uniform(1 - DAMAGE_VARIANCE, 1 + DAMAGE_VARIANCE)
    critical = rng.random() * 100 < stats_a["fate"]
    if critical:
        damage *= CRIT_MULTIPLIER

    effectiveness = None
    if affinity > 1:
        effectiveness = "strong"
    elif affinity < 1:
        effectiveness = "weak"

    return _lose_hp(
        defender,
        max(1, round(damage)),
        events,
        {"type": "damage", "source": attacker["id"], "critical": critical,
         "effectiveness": effectiveness, "kind": kind,
         **({"rival": True} if rival else {}), **(extra or {})},
    )


def _best_kind(unit):
    return "physical" if unit["stats"]["might"] >= unit["stats"]["arcana"] else "magical"


def _element_rider(state, caster, target, damage, events):
    element = caster["element"]
    if element == "ember":
        _apply_status(state, target, "burn", 2, events)
    elif element == "tide":
        _apply_status(state, target, "slow", 2, events)
    elif element == "gale":
        _apply_status(state, target, "expose", 2, events)
    elif element == "terra":
        _apply_status(state, target, "weaken", 2, events)
    elif element == "volt" and damage > 0:
        others = [u for u in _team(state, target["side"]) if u["id"] != target["id"]]
        if others:
            chained = min(others, key=lambda u: u["hp"] / u["maxHp"])
            _lose_hp(chained, max(1, round(damage * VOLT_CHAIN_RATIO)), events,
                     {"type": "damage", "source": caster["id"], "critical": False,
                      "effectiveness": None, "kind": "magical", "chain": True})
    elif element == "lumen" and damage > 0:
        allies = _team(state, caster["side"])
        wounded = min(allies, key=lambda u: u["hp"] / u["maxHp"])
        _heal(wounded, damage * LUMEN_HEAL_RATIO, events, source=caster)
    elif element == "umbra" and damage > 0:
        _heal(caster, damage * UMBRA_DRAIN_RATIO, events, source=caster)


# ------------------------------------------------------------ habilidades ---


def _strike(state, actor, targets, rng, events):
    _deal_damage(actor, targets[0], 1.0, _best_kind(actor), rng, events)
    _gain_aether(state, actor["side"], BASIC_SKILL_AETHER)


def _guard(state, actor, targets, rng, events):
    _apply_status(state, actor, "guard", 1, events)
    _gain_aether(state, actor["side"], BASIC_SKILL_AETHER)


def _bastion_call(state, actor, targets, rng, events):
    _apply_status(state, actor, "taunt", 2, events)
    _apply_status(state, actor, "shield", 3, events, value=round(actor["maxHp"] * 0.25))


def _tremor_slam(state, actor, targets, rng, events):
    for target in targets:
        _deal_damage(actor, target, 0.8, "physical", rng, events)
        if _alive(target) and rng.random() < 0.35:
            _apply_status(state, target, "stun", 1, events)


def _unbreakable_oath(state, actor, targets, rng, events):
    for target in targets:
        _apply_status(state, target, "shield", 3, events, value=round(actor["maxHp"] * 0.3))
        _apply_status(state, target, "guard", 1, events)


def _rending_flurry(state, actor, targets, rng, events):
    for _ in range(2):
        if _alive(targets[0]):
            _deal_damage(actor, targets[0], 0.75, "physical", rng, events)


def _execution_arc(state, actor, targets, rng, events):
    target = targets[0]
    multiplier = 1.5 * (1.6 if target["hp"] / target["maxHp"] < 0.4 else 1)
    _deal_damage(actor, target, multiplier, "physical", rng, events)


def _thousand_cuts(state, actor, targets, rng, events):
    for _ in range(5):
        alive = [t for t in targets if _alive(t)]
        if not alive:
            break
        target = rng.choice(alive)
        _deal_damage(actor, target, 0.55, "physical", rng, events)
        _apply_status(state, target, "weaken", 2, events)


def _elemental_bolt(state, actor, targets, rng, events):
    damage = _deal_damage(actor, targets[0], 1.45, "magical", rng, events)
    _element_rider(state, actor, targets[0], damage, events)


def _arcane_tempest(state, actor, targets, rng, events):
    for target in targets:
        damage = _deal_damage(actor, target, 0.8, "magical", rng, events)
        _element_rider(state, actor, target, damage, events)


def _cataclysm(state, actor, targets, rng, events):
    damage = _deal_damage(actor, targets[0], 2.3, "magical", rng, events, pierce=0.5)
    _element_rider(state, actor, targets[0], damage, events)


def _mending_light(state, actor, targets, rng, events):
    target = targets[0]
    _heal(target, actor["stats"]["arcana"] * 1.8 + target["maxHp"] * 0.05, events, source=actor)
    _cleanse(target, events)


def _sanctuary(state, actor, targets, rng, events):
    for target in targets:
        _heal(target, actor["stats"]["arcana"] * 1.0, events, source=actor)
        _apply_status(state, target, "regen", 3, events)


def _rebirth_hymn(state, actor, targets, rng, events):
    target = targets[0]
    target["hp"] = max(1, round(target["maxHp"] * 0.5))
    events.append({"type": "revive", "source": actor["id"], "target": target["id"],
                   "hp": target["hp"]})
    _apply_status(state, target, "empower", 2, events)


def _hexing_shiv(state, actor, targets, rng, events):
    target = targets[0]
    _deal_damage(actor, target, 1.0, "hybrid", rng, events)
    _apply_status(state, target, "weaken", 2, events)
    _apply_status(state, target, "expose", 2, events)


def _aether_siphon(state, actor, targets, rng, events):
    for target in targets:
        _deal_damage(actor, target, 0.5, "hybrid", rng, events)
        _apply_status(state, target, "slow", 2, events)
    enemy_side = _opponent(actor["side"])
    stolen = min(2, state["aether"][enemy_side])
    if stolen:
        state["aether"][enemy_side] -= stolen
        _gain_aether(state, actor["side"], stolen)
        events.append({"type": "aether", "source": actor["id"], "from": enemy_side,
                       "to": actor["side"], "amount": stolen})


def _grand_deception(state, actor, targets, rng, events):
    for target in targets:
        _deal_damage(actor, target, 0.9, "hybrid", rng, events)
    for ally in _team(state, actor["side"]):
        _cleanse(ally, events)
        _apply_status(state, ally, "empower", 2, events)


def _companion_attack(state, actor, rng, events):
    """O monstro do Invocador ataca um inimigo (respeitando a provocação)."""
    foe_side = _opponent(actor["side"])
    options = _taunters(state, foe_side) or _team(state, foe_side)
    if not options:
        return
    target = rng.choice(options)
    events.append({"type": "companion", "actor": actor["id"], "target": target["id"]})
    _deal_damage(actor, target, COMPANION_MULTIPLIER, "hybrid", rng, events,
                 extra={"companion": True})


def _call_companion(state, actor, targets, rng, events):
    _deal_damage(actor, targets[0], 0.8, "hybrid", rng, events)
    _apply_status(state, actor, "companion", COMPANION_TURNS, events)


def _beast_rampage(state, actor, targets, rng, events):
    bonded = _has(actor, "companion")
    for target in targets:
        _deal_damage(actor, target, 0.75, "hybrid", rng, events)
        if bonded:
            _apply_status(state, target, "expose", 2, events)


def _primal_awakening(state, actor, targets, rng, events):
    _deal_damage(actor, targets[0], 2.0, "hybrid", rng, events)
    _apply_status(state, actor, "companion", COMPANION_TURNS, events)
    _apply_status(state, actor, "empower", 2, events)


# role: usado pela IA. attack | heal | revive | buff | defend
SKILLS = {
    "strike": {
        "name": "Strike", "cost": 0, "target": "enemy", "role": "attack",
        "description": "Basic attack with the card's best power. Generates +1 extra Aether.",
        "effect": _strike,
    },
    "guard": {
        "name": "Guard", "cost": 0, "target": "self", "role": "defend",
        "description": "Halves damage taken until this card's next turn. "
                       "Generates +1 extra Aether.",
        "effect": _guard,
    },
    # Vanguard
    "bastion_call": {
        "name": "Bastion Call", "cost": 3, "target": "self", "role": "buff",
        "description": "Taunts all foes for 2 turns and raises a shield worth "
                       "25% of max vitality.",
        "effect": _bastion_call,
    },
    "tremor_slam": {
        "name": "Tremor Slam", "cost": 5, "target": "all_enemies", "role": "attack",
        "description": "Physical blow to every foe (0.8x) with 35% chance to Stun each.",
        "effect": _tremor_slam,
    },
    "unbreakable_oath": {
        "name": "Unbreakable Oath", "cost": 7, "target": "all_allies", "role": "buff",
        "description": "Supreme. Shields every ally for 30% of this card's max "
                       "vitality and puts them on Guard.",
        "effect": _unbreakable_oath,
    },
    # Duelist
    "rending_flurry": {
        "name": "Rending Flurry", "cost": 3, "target": "enemy", "role": "attack",
        "description": "Two quick physical slashes (0.75x each).",
        "effect": _rending_flurry,
    },
    "execution_arc": {
        "name": "Execution Arc", "cost": 5, "target": "enemy", "role": "attack",
        "description": "Heavy physical strike (1.5x), 60% stronger against foes "
                       "below 40% vitality.",
        "effect": _execution_arc,
    },
    "thousand_cuts": {
        "name": "Thousand Cuts", "cost": 7, "target": "all_enemies", "role": "attack",
        "description": "Supreme. Five physical slashes (0.55x) on random foes, "
                       "each one Weakening its target.",
        "effect": _thousand_cuts,
    },
    # Arcanist
    "elemental_bolt": {
        "name": "Elemental Bolt", "cost": 3, "target": "enemy", "role": "attack",
        "description": "Magical bolt (1.45x) carrying this card's element effect.",
        "effect": _elemental_bolt,
    },
    "arcane_tempest": {
        "name": "Arcane Tempest", "cost": 5, "target": "all_enemies", "role": "attack",
        "description": "Magical storm (0.8x) on every foe, each hit carrying the "
                       "element effect.",
        "effect": _arcane_tempest,
    },
    "cataclysm": {
        "name": "Cataclysm", "cost": 7, "target": "enemy", "role": "attack",
        "description": "Supreme. Devastating spell (2.3x) that ignores half of the "
                       "target's Resolve, with the element effect.",
        "effect": _cataclysm,
    },
    # Mystic
    "mending_light": {
        "name": "Mending Light", "cost": 3, "target": "ally", "role": "heal",
        "description": "Heals one ally based on Arcana and removes its debuffs.",
        "effect": _mending_light,
    },
    "sanctuary": {
        "name": "Sanctuary", "cost": 5, "target": "all_allies", "role": "heal",
        "description": "Heals every ally and grants Regen for 3 turns.",
        "effect": _sanctuary,
    },
    "rebirth_hymn": {
        "name": "Rebirth Hymn", "cost": 7, "target": "fallen_ally", "role": "revive",
        "description": "Supreme. Brings a fallen ally back with 50% vitality and "
                       "Empowers it.",
        "effect": _rebirth_hymn,
    },
    # Trickster
    "hexing_shiv": {
        "name": "Hexing Shiv", "cost": 3, "target": "enemy", "role": "attack",
        "description": "Cursed stab (1.0x hybrid) that Weakens and Exposes the target.",
        "effect": _hexing_shiv,
    },
    "aether_siphon": {
        "name": "Aether Siphon", "cost": 5, "target": "all_enemies", "role": "attack",
        "description": "Light hybrid hit (0.5x) that Slows every foe and steals up "
                       "to 2 of their Aether.",
        "effect": _aether_siphon,
    },
    "grand_deception": {
        "name": "Grand Deception", "cost": 7, "target": "all_enemies", "role": "attack",
        "description": "Supreme. Hybrid hit (0.9x) on every foe, then cleanses and "
                       "Empowers all allies.",
        "effect": _grand_deception,
    },
    # Summoner
    "call_companion": {
        "name": "Call Companion", "cost": 3, "target": "enemy", "role": "attack",
        "description": "The bonded monster pounces on a foe (0.8x hybrid) and stays "
                       "for 3 turns as a Companion.",
        "effect": _call_companion,
    },
    "beast_rampage": {
        "name": "Beast Rampage", "cost": 5, "target": "all_enemies", "role": "attack",
        "description": "Hybrid assault on every foe (0.75x). With a Companion out, "
                       "also Exposes them.",
        "effect": _beast_rampage,
    },
    "primal_awakening": {
        "name": "Primal Awakening", "cost": 7, "target": "enemy", "role": "attack",
        "description": "Supreme. The monster reveals its true form: massive hybrid "
                       "blow (2.0x), then stays as a Companion and Empowers this card.",
        "effect": _primal_awakening,
    },
}

ARCHETYPE_SKILLS = {
    "vanguard": ("bastion_call", "tremor_slam", "unbreakable_oath"),
    "duelist": ("rending_flurry", "execution_arc", "thousand_cuts"),
    "arcanist": ("elemental_bolt", "arcane_tempest", "cataclysm"),
    "mystic": ("mending_light", "sanctuary", "rebirth_hymn"),
    "trickster": ("hexing_shiv", "aether_siphon", "grand_deception"),
    "summoner": ("call_companion", "beast_rampage", "primal_awakening"),
}

BASIC_SKILLS = ("strike", "guard")


# Todo arquétipo tem 3 habilidades (a última é a suprema).
ARCHETYPE_SKILL_SLOTS = 3


def archetype_skill_count(rarity, ascension=0):
    """Quantas habilidades do arquétipo a carta conhece (raridade + ascensão)."""
    return min(ARCHETYPE_SKILL_SLOTS, max(1, rarity - 2) + bonus_skills(ascension))


def skills_for(character, ascension=0):
    """Habilidades da carta: básicas + do arquétipo conforme raridade e ascensão."""
    unlocked = archetype_skill_count(character["rarity"], ascension)
    return [*BASIC_SKILLS, *ARCHETYPE_SKILLS[character["archetype"]][:unlocked]]


def ascension_unlocks_skill(character):
    """Se a ascensão máxima ensina uma habilidade nova a esta carta."""
    rarity = character["rarity"]
    return archetype_skill_count(rarity, MAX_ASCENSION) > archetype_skill_count(rarity)


def public_skill(skill_id):
    skill = SKILLS[skill_id]
    return {
        "id": skill_id,
        "name": skill["name"],
        "description": skill["description"],
        "cost": skill["cost"],
        "target": skill["target"],
    }


def public_skills(character, ascension=0):
    return [public_skill(skill_id) for skill_id in skills_for(character, ascension)]


# ----------------------------------------------------------- montagem ---


def build_unit(character, side, index, level, power=1.0, ascension=0):
    """Combatente da batalha. `power` multiplica os atributos grandes (dificuldade)."""
    ascension = clamp_ascension(ascension)
    stats = battle_stats(character, level, ascension)
    for stat in SCALED_STATS:
        stats[stat] = max(1, round(stats[stat] * power))
    return {
        "id": f"{'p' if side == 'player' else 'e'}{index}",
        "side": side,
        "fileName": character["file_name"],
        "name": character["name"],
        "rarity": character["rarity"],
        "element": character["element"],
        "archetype": character["archetype"],
        "level": level,
        "ascension": ascension,
        "stats": stats,
        "maxHp": stats["vitality"],
        "hp": stats["vitality"],
        "statuses": {},
        "skills": skills_for(character, ascension),
    }


def _link_bonds(state, events):
    """Liga laços (mesmo time, bônus de atributos) e rivalidades (times opostos)."""
    for unit in state["units"]:
        unit["bonds"] = []
        unit["rivals"] = []
    for i, unit in enumerate(state["units"]):
        for other in state["units"][i + 1:]:
            if other["side"] != unit["side"]:
                lines = rivalry_between(unit["fileName"], other["fileName"])
                if lines:
                    unit["rivals"].append(other["id"])
                    other["rivals"].append(unit["id"])
                    events.append({"type": "rivalry", "actor": unit["id"],
                                   "target": other["id"], "line": lines[0],
                                   "reply": lines[1]})
                continue
            lines = bond_between(unit["fileName"], other["fileName"])
            if not lines:
                continue
            unit["bonds"].append(other["id"])
            other["bonds"].append(unit["id"])
            events.append({"type": "bond", "actor": unit["id"], "target": other["id"],
                           "line": lines[0], "reply": lines[1]})
    for unit in state["units"]:
        if not unit["bonds"]:
            continue
        bonus = 1 + BOND_STAT_BONUS * len(unit["bonds"])
        for stat in SCALED_STATS:
            unit["stats"][stat] = round(unit["stats"][stat] * bonus)
        unit["maxHp"] = unit["hp"] = unit["stats"]["vitality"]


def _bond_grief(state, events, start):
    """Parceiros de laço de quem caiu (nos eventos desde `start`) ganham Fortalecer."""
    fallen = [e["target"] for e in events[start:] if e["type"] == "defeated"]
    for fallen_id in fallen:
        unit = _unit(state, fallen_id)
        for partner_id in unit.get("bonds", []):
            partner = _unit(state, partner_id)
            if not _alive(partner):
                continue
            events.append({"type": "bondGrief", "target": partner_id, "source": fallen_id})
            _apply_status(state, partner, "empower", BOND_GRIEF_TURNS, events)


def enemy_level(player_level, difficulty):
    offset = DIFFICULTIES[difficulty]["levelOffset"]
    return max(1, min(MAX_LEVEL, player_level + offset))


def draw_enemy_team(difficulty, rng):
    """Sorteia TEAM_SIZE cartas distintas com os pesos de raridade da dificuldade."""
    weights_by_rarity = DIFFICULTIES[difficulty]["rarityWeights"]
    counts = {}
    for character in CHARACTERS:
        counts[character["rarity"]] = counts.get(character["rarity"], 0) + 1

    available = list(CHARACTERS)
    team = []
    for _ in range(TEAM_SIZE):
        # Peso da raridade dividido entre as cartas dela.
        weights = [
            weights_by_rarity[c["rarity"]] / counts[c["rarity"]] for c in available
        ]
        character = rng.choices(available, weights=weights, k=1)[0]
        available.remove(character)
        team.append(character)
    return team


def unlocked_difficulties(player_level):
    return [key for key, d in DIFFICULTIES.items() if player_level >= d["minLevel"]]


def public_difficulties(player_level):
    return [
        {
            "id": key,
            "label": d["label"],
            "description": d["description"],
            "minLevel": d["minLevel"],
            "unlocked": player_level >= d["minLevel"],
            "enemyLevel": enemy_level(player_level, key),
            "experience": d["experience"],
        }
        for key, d in DIFFICULTIES.items()
    ]


def create_battle(battle_id, player_team, player_level, difficulty, rng, enemy_team=None,
                  ascensions=None):
    """Monta a batalha e roda os turnos até a vez do jogador.

    `player_team`: definições (de `cards.py`) das cartas escolhidas.
    `ascensions`: {file_name: ascensão} das cartas do jogador (lido no servidor).
    Devolve (estado, eventos).
    """
    if difficulty not in DIFFICULTIES:
        raise BattleError("Unknown difficulty.")
    if difficulty not in unlocked_difficulties(player_level):
        raise BattleError(
            f"{DIFFICULTIES[difficulty]['label']} unlocks at level "
            f"{DIFFICULTIES[difficulty]['minLevel']}."
        )
    if len(player_team) != TEAM_SIZE:
        raise BattleError(f"Choose exactly {TEAM_SIZE} cards.")
    if len({c["file_name"] for c in player_team}) != TEAM_SIZE:
        raise BattleError("Choose different cards.")

    foes = enemy_team or draw_enemy_team(difficulty, rng)
    foe_level = enemy_level(player_level, difficulty)
    state = {
        "battleId": battle_id,
        "difficulty": difficulty,
        "status": "active",
        "endReason": None,
        "round": 0,
        "queue": [],
        "turn": None,
        "acting": None,
        "aether": {"player": STARTING_AETHER, "enemy": STARTING_AETHER},
        "playerLevel": player_level,
        "enemyLevel": foe_level,
        "units": [
            *(
                build_unit(c, "player", i, player_level,
                           ascension=(ascensions or {}).get(c["file_name"], 0))
                for i, c in enumerate(player_team)
            ),
            *(
                build_unit(c, "enemy", i, foe_level, DIFFICULTIES[difficulty]["enemyPower"])
                for i, c in enumerate(foes)
            ),
        ],
    }
    events = []
    _link_bonds(state, events)
    _advance(state, rng, events)
    return state, events


def create_pvp_battle(battle_id, challenger_team, challenger_level, opponent_team,
                      opponent_level, rng, challenger_ascensions=None,
                      opponent_ascensions=None):
    """Duelo entre dois jogadores: quem desafiou é "player", quem aceitou "enemy".

    Cada time luta no nível e com as ascensões do seu dono.
    Devolve (estado, eventos) parado na vez da primeira carta.
    """
    for team in (challenger_team, opponent_team):
        if len(team) != TEAM_SIZE:
            raise BattleError(f"Choose exactly {TEAM_SIZE} cards.")
        if len({c["file_name"] for c in team}) != TEAM_SIZE:
            raise BattleError("Choose different cards.")

    state = {
        "battleId": battle_id,
        "mode": "pvp",
        "difficulty": None,
        "status": "active",
        "endReason": None,
        "round": 0,
        "queue": [],
        "turn": None,
        "acting": None,
        "aether": {"player": STARTING_AETHER, "enemy": STARTING_AETHER},
        "playerLevel": challenger_level,
        "enemyLevel": opponent_level,
        "units": [
            *(
                build_unit(c, "player", i, challenger_level,
                           ascension=(challenger_ascensions or {}).get(c["file_name"], 0))
                for i, c in enumerate(challenger_team)
            ),
            *(
                build_unit(c, "enemy", i, opponent_level,
                           ascension=(opponent_ascensions or {}).get(c["file_name"], 0))
                for i, c in enumerate(opponent_team)
            ),
        ],
    }
    events = []
    _link_bonds(state, events)
    _advance(state, rng, events)
    return state, events


# ----------------------------------------------------------------- turnos ---


def effective_celerity(unit):
    celerity = unit["stats"]["celerity"]
    return celerity * SLOW_MULTIPLIER if _has(unit, "slow") else celerity


def is_pvp(state):
    return state.get("mode") == "pvp"


def human_sides(state):
    """Lados controlados por jogadores (os outros são do computador)."""
    return ("player", "enemy") if is_pvp(state) else ("player",)


def _start_round(state, rng, events):
    state["round"] += 1
    if state["round"] > MAX_ROUNDS:
        state["round"] = MAX_ROUNDS
        # Contra o computador, demorar demais é derrota; entre jogadores, empate.
        _finish(state, "draw" if is_pvp(state) else "lost", "timeout", events)
        return
    living = [u for u in state["units"] if _alive(u)]
    # Desempate aleatório entre velocidades iguais.
    living.sort(key=lambda u: (effective_celerity(u), rng.random()), reverse=True)
    state["queue"] = [u["id"] for u in living]
    events.append({"type": "round", "round": state["round"], "order": state["queue"]})


def _next_actor(state, rng, events):
    while state["status"] == "active":
        if not state["queue"]:
            _start_round(state, rng, events)
            continue
        unit = _unit(state, state["queue"].pop(0))
        if unit and _alive(unit):
            return unit
    return None


def _start_turn(state, actor, events, rng=None):
    """Efeitos do início do turno. Devolve False se o combatente não age."""
    actor["statuses"].pop("guard", None)
    _gain_aether(state, actor["side"], AETHER_PER_TURN)
    events.append({"type": "turn", "actor": actor["id"], "aether": dict(state["aether"])})

    if _has(actor, "burn"):
        amount = max(1, round(actor["maxHp"] * BURN_RATIO))
        _lose_hp(actor, amount, events, {"type": "damage", "status": "burn",
                                         "critical": False, "effectiveness": None})
        if not _alive(actor):
            return False
    if _has(actor, "regen"):
        _heal(actor, actor["maxHp"] * REGEN_RATIO, events, status="regen")
    if _has(actor, "companion"):
        _companion_attack(state, actor, rng or random.Random(), events)
        if not _team(state, _opponent(actor["side"])):
            return False
    if _has(actor, "stun"):
        del actor["statuses"]["stun"]
        events.append({"type": "stunned", "target": actor["id"]})
        _end_turn(state, actor)
        return False
    return True


def _end_turn(state, actor):
    for status in list(actor["statuses"]):
        # Guarda dura até o começo do próximo turno (sai em _start_turn).
        if status == "guard":
            continue
        actor["statuses"][status]["turns"] -= 1
        if actor["statuses"][status]["turns"] <= 0:
            del actor["statuses"][status]
    state["acting"] = None


def _finish(state, result, reason, events):
    state["status"] = result
    state["endReason"] = reason
    state["turn"] = None
    state["queue"] = []
    events.append({"type": "end", "result": result, "reason": reason})


def _check_end(state, events):
    if state["status"] != "active":
        return True
    if not _team(state, "enemy"):
        _finish(state, "won", "victory", events)
        return True
    if not _team(state, "player"):
        _finish(state, "lost", "defeat", events)
        return True
    return False


def _advance(state, rng, events):
    """Roda turnos até ser a vez de uma carta do jogador ou a batalha acabar."""
    state["turn"] = None
    while state["status"] == "active":
        actor = _next_actor(state, rng, events)
        if actor is None:
            return
        state["acting"] = actor["id"]
        start = len(events)
        acts = _start_turn(state, actor, events, rng)
        _bond_grief(state, events, start)
        if _check_end(state, events):
            return
        if not acts:
            state["acting"] = None
            continue
        if actor["side"] in human_sides(state):
            state["turn"] = actor["id"]
            return
        skill_id, target_id = choose_action(state, actor, rng)
        _perform(state, actor, skill_id, target_id, rng, events)
        _end_turn(state, actor)
        if _check_end(state, events):
            return


# ----------------------------------------------------------------- alvos ---


def _taunters(state, side):
    return [u for u in _team(state, side) if _has(u, "taunt")]


def valid_targets(state, actor, skill_id):
    """Ids dos alvos possíveis da habilidade (lista vazia = não há alvo)."""
    target = SKILLS[skill_id]["target"]
    allies = _team(state, actor["side"])
    enemies = _team(state, _opponent(actor["side"]))
    if target == "enemy":
        return [u["id"] for u in (_taunters(state, _opponent(actor["side"])) or enemies)]
    if target == "ally":
        return [u["id"] for u in allies]
    if target == "fallen_ally":
        return [u["id"] for u in _team(state, actor["side"], alive=False)]
    if target == "self":
        return [actor["id"]]
    if target == "all_enemies":
        return [u["id"] for u in enemies]
    return [u["id"] for u in allies]


def _resolve_targets(state, actor, skill_id, target_id):
    target = SKILLS[skill_id]["target"]
    options = valid_targets(state, actor, skill_id)
    if not options:
        raise BattleError("This skill has no valid target.")
    if target in ("enemy", "ally", "fallen_ally"):
        if target_id is None and len(options) == 1:
            target_id = options[0]
        if target_id not in options:
            if target == "enemy" and _taunters(state, _opponent(actor["side"])):
                raise BattleError("A taunting foe must be targeted first.")
            raise BattleError("Invalid target.")
        return [_unit(state, target_id)]
    return [_unit(state, unit_id) for unit_id in options]


def skill_unavailable_reason(state, actor, skill_id):
    if skill_id not in actor["skills"]:
        return "This card does not know this skill."
    if state["aether"][actor["side"]] < SKILLS[skill_id]["cost"]:
        return "Not enough Aether."
    if not valid_targets(state, actor, skill_id):
        return "No valid target."
    return None


def _perform(state, actor, skill_id, target_id, rng, events):
    targets = _resolve_targets(state, actor, skill_id, target_id)
    skill = SKILLS[skill_id]
    state["aether"][actor["side"]] -= skill["cost"]
    events.append({"type": "skill", "actor": actor["id"], "skill": skill_id,
                   "skillName": skill["name"], "targets": [t["id"] for t in targets],
                   "aether": dict(state["aether"])})
    start = len(events)
    skill["effect"](state, actor, targets, rng, events)
    _bond_grief(state, events, start)


# --------------------------------------------------------------------- IA ---


def _hp_ratio(unit):
    return unit["hp"] / unit["maxHp"]


def _pick_enemy_target(state, actor, options):
    """Prefere vantagem elemental e alvos feridos."""
    def score(unit_id):
        unit = _unit(state, unit_id)
        return _hp_ratio(unit) / element_multiplier(actor["element"], unit["element"])

    return min(options, key=score)


def choose_action(state, actor, rng):
    """Decide (habilidade, alvo) para uma carta controlada pelo computador."""
    usable = [s for s in actor["skills"] if skill_unavailable_reason(state, actor, s) is None]
    allies = _team(state, actor["side"])
    by_role = {}
    for skill_id in usable:
        by_role.setdefault(SKILLS[skill_id]["role"], []).append(skill_id)

    if "revive" in by_role:
        fallen = valid_targets(state, actor, "rebirth_hymn")
        return "rebirth_hymn", fallen[0]

    heals = by_role.get("heal", [])
    wounded = [u for u in allies if _hp_ratio(u) < 0.5]
    if "sanctuary" in heals and len([u for u in allies if _hp_ratio(u) < 0.65]) >= 2:
        return "sanctuary", None
    if "mending_light" in heals and wounded:
        return "mending_light", min(wounded, key=_hp_ratio)["id"]

    if "bastion_call" in usable and not _has(actor, "taunt") and rng.random() < 0.7:
        return "bastion_call", None
    if "unbreakable_oath" in usable and any(_hp_ratio(u) < 0.6 for u in allies):
        return "unbreakable_oath", None

    attacks = [s for s in by_role.get("attack", []) if s != "strike"]
    # Prefere a habilidade mais cara que dá para pagar; às vezes guarda Aether.
    attacks.sort(key=lambda s: SKILLS[s]["cost"], reverse=True)
    if attacks and rng.random() < 0.75:
        skill_id = attacks[0]
    elif _hp_ratio(actor) < 0.3 and rng.random() < 0.35:
        return "guard", None
    else:
        skill_id = "strike"

    if SKILLS[skill_id]["target"] == "enemy":
        return skill_id, _pick_enemy_target(state, actor, valid_targets(state, actor, skill_id))
    return skill_id, None


# ---------------------------------------------------------- ação do jogador ---


def withdraw(state, side, reason, events):
    """O lado `side` sai da batalha (desistência ou abandono) e perde."""
    _finish(state, "lost" if side == "player" else "won", reason, events)


def play_turn(state, action, rng, side="player"):
    """Executa a ação do lado `side` na carta da vez e roda os turnos do computador.

    `action`: {"type": "skill", "skill": id, "target": unitId | None},
    {"type": "auto"} (o computador decide pelo jogador) ou {"type": "forfeit"}.
    Desistir vale a qualquer momento; as outras ações só na vez de uma carta
    de `side`. Devolve a lista de eventos. Lança BattleError se a ação for
    inválida.
    """
    if state["status"] != "active":
        raise BattleError("This battle is over.")

    events = []
    action_type = action.get("type")

    if action_type == "forfeit":
        withdraw(state, side, "forfeit", events)
        return events

    if not state["turn"]:
        raise BattleError("This battle is over.")
    actor = _unit(state, state["turn"])
    if actor["side"] != side:
        raise BattleError("It is not your turn.")
    if action_type == "auto":
        skill_id, target_id = choose_action(state, actor, rng)
    elif action_type == "skill":
        skill_id, target_id = action.get("skill"), action.get("target")
        if not isinstance(skill_id, str) or skill_id not in SKILLS:
            raise BattleError("Unknown skill.")
        if target_id is not None and not isinstance(target_id, str):
            raise BattleError("Invalid target.")
        reason = skill_unavailable_reason(state, actor, skill_id)
        if reason:
            raise BattleError(reason)
    else:
        raise BattleError("Unknown action.")

    state["acting"] = actor["id"]
    _perform(state, actor, skill_id, target_id, rng, events)
    _end_turn(state, actor)
    if not _check_end(state, events):
        _advance(state, rng, events)
    return events


# --------------------------------------------------------------- recompensa ---


def defeated_enemies(state, side="player"):
    """Cartas do adversário de `side` que estão derrotadas."""
    return len(_team(state, _opponent(side), alive=False))


def outcome_for(state, side="player"):
    """Resultado visto pelo lado `side`: active, won, lost ou draw."""
    status = state["status"]
    if side == "enemy" and status in ("won", "lost"):
        return "lost" if status == "won" else "won"
    return status


def _win_experience(state):
    if is_pvp(state):
        return PVP["experience"]
    return DIFFICULTIES[state["difficulty"]]["experience"]


def battle_experience(state, side="player"):
    """Experiência ganha por `side` ao fim da batalha (0 se ainda estiver ativa)."""
    base = _win_experience(state)
    outcome = outcome_for(state, side)
    if outcome == "won":
        return base
    if outcome == "lost" and state["endReason"] in WITHDRAW_REASONS:
        return 0
    if outcome in ("lost", "draw"):
        return round(base * LOSS_EXPERIENCE_RATIO) + (
            LOSS_EXPERIENCE_PER_DEFEAT * defeated_enemies(state, side)
        )
    return 0


# ------------------------------------------------------------ visão pública ---


def _flip_id(unit_id):
    """p0 <-> e0: ids vistos pelo lado "enemy" (o próprio time vira "p")."""
    if not isinstance(unit_id, str) or not unit_id:
        return unit_id
    prefix = {"p": "e", "e": "p"}.get(unit_id[0])
    return prefix + unit_id[1:] if prefix else unit_id


def view_id(unit_id, viewer):
    """Id de uma carta como `viewer` vê (a conversão é a mesma nos dois sentidos)."""
    return _flip_id(unit_id) if viewer == "enemy" else unit_id


def _view_side(side, viewer):
    if viewer == "enemy" and side in ("player", "enemy"):
        return _opponent(side)
    return side


def _view_aether(aether, viewer):
    return {_view_side(side, viewer): value for side, value in aether.items()}


def view_reason(reason, outcome):
    """Motivo do fim visto por quem teve `outcome`.

    "victory"/"defeat" seguem o resultado de quem vê; quem venceu porque o
    outro saiu vê "opponent_forfeit"/"opponent_abandon".
    """
    if reason in ("victory", "defeat") and outcome in ("won", "lost"):
        return "victory" if outcome == "won" else "defeat"
    if reason in WITHDRAW_REASONS and outcome == "won":
        return f"opponent_{reason}"
    return reason


_EVENT_ID_FIELDS = ("actor", "target", "source")
_EVENT_ID_LIST_FIELDS = ("targets", "order")


def view_events(events, viewer="player"):
    """Eventos como `viewer` vê (próprio time como "player")."""
    viewed = []
    for event in events:
        event = dict(event)
        if viewer == "enemy":
            for field in _EVENT_ID_FIELDS:
                if field in event:
                    event[field] = _flip_id(event[field])
            for field in _EVENT_ID_LIST_FIELDS:
                if field in event:
                    event[field] = [_flip_id(unit_id) for unit_id in event[field]]
            if isinstance(event.get("aether"), dict):
                event["aether"] = _view_aether(event["aether"], viewer)
            for field in ("from", "to"):
                if field in event:
                    event[field] = _view_side(event[field], viewer)
            if event.get("type") == "end" and event["result"] in ("won", "lost"):
                event["result"] = "lost" if event["result"] == "won" else "won"
        if event.get("type") == "end":
            event["reason"] = view_reason(event["reason"], event["result"])
        viewed.append(event)
    return viewed


def _public_unit(unit, viewer="player"):
    return {
        "id": view_id(unit["id"], viewer),
        "side": _view_side(unit["side"], viewer),
        "fileName": unit["fileName"],
        "name": unit["name"],
        "rarity": unit["rarity"],
        "element": unit["element"],
        "elementLabel": ELEMENTS[unit["element"]]["label"],
        "archetype": unit["archetype"],
        "archetypeLabel": ARCHETYPES[unit["archetype"]]["label"],
        "level": unit["level"],
        "ascension": unit.get("ascension", 0),
        "bonds": [view_id(unit_id, viewer) for unit_id in unit.get("bonds", [])],
        "rivals": [view_id(unit_id, viewer) for unit_id in unit.get("rivals", [])],
        "stats": unit["stats"],
        "maxHp": unit["maxHp"],
        "hp": unit["hp"],
        "alive": _alive(unit),
        "statuses": [
            {
                "id": status,
                "label": STATUSES[status]["label"],
                "kind": STATUSES[status]["kind"],
                "description": STATUSES[status]["description"],
                "turns": entry["turns"],
                **({"value": entry["value"]} if "value" in entry else {}),
            }
            for status, entry in unit["statuses"].items()
        ],
        "skills": [public_skill(skill_id) for skill_id in unit["skills"]],
    }


def public_state(state, viewer="player"):
    """O que o lado `viewer` vê da batalha (tudo calculado aqui).

    O time de quem vê sempre aparece como "player" (ids "p0".."p2").
    """
    actor = _unit(state, state["turn"]) if state["turn"] else None
    your_turn = bool(actor) and state["status"] == "active" and actor["side"] == viewer
    actions = []
    if your_turn:
        for skill_id in actor["skills"]:
            reason = skill_unavailable_reason(state, actor, skill_id)
            targets = valid_targets(state, actor, skill_id) if reason is None else []
            actions.append(
                {
                    **public_skill(skill_id),
                    "usable": reason is None,
                    "reason": reason,
                    "targets": [view_id(unit_id, viewer) for unit_id in targets],
                }
            )

    pvp = is_pvp(state)
    outcome = outcome_for(state, viewer)
    return {
        "battleId": state["battleId"],
        "mode": "pvp" if pvp else "pve",
        "status": outcome,
        "endReason": view_reason(state["endReason"], outcome),
        "difficulty": "pvp" if pvp else state["difficulty"],
        "difficultyLabel": PVP["label"] if pvp else DIFFICULTIES[state["difficulty"]]["label"],
        "round": state["round"],
        "maxRounds": MAX_ROUNDS,
        "aether": _view_aether(state["aether"], viewer),
        "maxAether": MAX_AETHER,
        "turn": view_id(state["turn"], viewer),
        "yourTurn": your_turn,
        "upcoming": [
            view_id(unit_id, viewer)
            for unit_id in state["queue"]
            if _alive(_unit(state, unit_id))
        ],
        "units": [_public_unit(unit, viewer) for unit in state["units"]],
        "actions": actions,
        "elementRiders": {
            key: ELEMENT_RIDERS[key] for key in {u["element"] for u in state["units"]}
        },
    }


def new_rng():
    """Gerador de números aleatórios para uma requisição."""
    return random.SystemRandom()
