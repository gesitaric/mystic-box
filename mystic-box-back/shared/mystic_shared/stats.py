"""Atributos de batalha das cartas.

Cada carta (em `cards.py`) tem um elemento e um arquétipo. Os atributos de
batalha saem da raridade, do arquétipo e de uma "assinatura" fixa por carta
(pequena variação calculada a partir do `file_name`), então duas cartas do
mesmo arquétipo e raridade nunca são idênticas.

Atributos:
- vitality: pontos de vida.
- might: força física (golpes de arma).
- arcana: poder mágico (feitiços e curas).
- bulwark: defesa contra dano físico.
- resolve: defesa contra dano mágico.
- celerity: velocidade; quem tem mais age primeiro na rodada.
- fate: chance (%) de acerto crítico.

Tudo aqui é regra do jogo e fica SÓ no backend.
"""

import hashlib

from .ascension import stat_multiplier

STAT_KEYS = ("vitality", "might", "arcana", "bulwark", "resolve", "celerity", "fate")

STAT_LABELS = {
    "vitality": "Vitality",
    "might": "Might",
    "arcana": "Arcana",
    "bulwark": "Bulwark",
    "resolve": "Resolve",
    "celerity": "Celerity",
    "fate": "Fate",
}

STAT_DESCRIPTIONS = {
    "vitality": "Hit points. At 0 the card falls.",
    "might": "Physical power: Strike (when higher than Arcana) and weapon skills.",
    "arcana": "Magical power: spells and heals.",
    "bulwark": "Defense against physical damage.",
    "resolve": "Defense against magical damage.",
    "celerity": "Speed. Higher Celerity acts earlier in the round.",
    "fate": "Chance (%) of a critical hit.",
}

# Ciclo de afinidades: cada elemento domina o seguinte
# (ember > gale > terra > volt > tide > ember). Lumen e umbra dominam um ao outro.
ELEMENTS = {
    "ember": {"label": "Ember", "strong_against": ("gale",)},
    "gale": {"label": "Gale", "strong_against": ("terra",)},
    "terra": {"label": "Terra", "strong_against": ("volt",)},
    "volt": {"label": "Volt", "strong_against": ("tide",)},
    "tide": {"label": "Tide", "strong_against": ("ember",)},
    "lumen": {"label": "Lumen", "strong_against": ("umbra",)},
    "umbra": {"label": "Umbra", "strong_against": ("lumen",)},
}

ADVANTAGE_MULTIPLIER = 1.3
DISADVANTAGE_MULTIPLIER = 0.8

ARCHETYPES = {
    "vanguard": {
        "label": "Vanguard",
        "description": "Stalwart guardian who draws fire and shields allies.",
        "base": {"vitality": 135, "might": 22, "arcana": 10, "bulwark": 25,
                 "resolve": 19, "celerity": 9, "fate": 5},
    },
    "duelist": {
        "label": "Duelist",
        "description": "Swift blade that strikes hard and often.",
        "base": {"vitality": 98, "might": 31, "arcana": 8, "bulwark": 15,
                 "resolve": 12, "celerity": 15, "fate": 14},
    },
    "arcanist": {
        "label": "Arcanist",
        "description": "Wielder of raw elements, fragile but devastating.",
        "base": {"vitality": 92, "might": 8, "arcana": 33, "bulwark": 12,
                 "resolve": 19, "celerity": 12, "fate": 9},
    },
    "mystic": {
        "label": "Mystic",
        "description": "Channels light and life to mend and revive allies.",
        "base": {"vitality": 104, "might": 10, "arcana": 25, "bulwark": 14,
                 "resolve": 23, "celerity": 11, "fate": 6},
    },
    "trickster": {
        "label": "Trickster",
        "description": "Cunning schemer who curses foes and steals Aether.",
        "base": {"vitality": 92, "might": 25, "arcana": 25, "bulwark": 12,
                 "resolve": 14, "celerity": 18, "fate": 12},
    },
    "summoner": {
        "label": "Summoner",
        "description": "Fights beside a bonded monster that keeps striking foes.",
        "base": {"vitality": 100, "might": 24, "arcana": 27, "bulwark": 15,
                 "resolve": 18, "celerity": 13, "fate": 9},
    },
}

# Multiplicador dos atributos "grandes" por raridade.
RARITY_SCALE = {3: 1.0, 4: 1.2, 5: 1.45}
# Velocidade e crítico crescem somando, não multiplicando.
RARITY_CELERITY_BONUS = {3: 0, 4: 1, 5: 2}
RARITY_FATE_BONUS = {3: 0, 4: 2, 5: 4}

SCALED_STATS = ("vitality", "might", "arcana", "bulwark", "resolve")

# Variação máxima da assinatura de cada carta (+/- 8%).
SIGNATURE_SPREAD = 0.08

# Cada nível acima do 1 aumenta os atributos grandes em 3%.
LEVEL_STAT_BONUS = 0.03

MAX_FATE = 50


def _signature(file_name, stat):
    """Variação fixa entre 1 - SPREAD e 1 + SPREAD para a carta e o atributo."""
    digest = hashlib.sha256(f"{file_name}:{stat}".encode()).digest()
    fraction = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return 1 + (fraction * 2 - 1) * SIGNATURE_SPREAD


def level_multiplier(level):
    return 1 + LEVEL_STAT_BONUS * (max(1, int(level)) - 1)


def battle_stats(character, level=1, ascension=0):
    """Atributos de batalha da carta no nível `level` e na ascensão `ascension`."""
    archetype = ARCHETYPES[character["archetype"]]
    rarity = character["rarity"]
    scale = RARITY_SCALE[rarity] * level_multiplier(level) * stat_multiplier(ascension)
    stats = {}

    for stat in STAT_KEYS:
        value = archetype["base"][stat] * _signature(character["file_name"], stat)
        if stat in SCALED_STATS:
            value *= scale
        elif stat == "celerity":
            value += RARITY_CELERITY_BONUS[rarity]
        else:
            value += RARITY_FATE_BONUS[rarity]
        stats[stat] = max(1, round(value))

    stats["fate"] = min(stats["fate"], MAX_FATE)
    return stats


def element_multiplier(attacker_element, defender_element):
    """Multiplicador de dano do elemento do atacante contra o do defensor."""
    if defender_element in ELEMENTS[attacker_element]["strong_against"]:
        return ADVANTAGE_MULTIPLIER
    if attacker_element in ELEMENTS[defender_element]["strong_against"]:
        return DISADVANTAGE_MULTIPLIER
    return 1.0


def public_battle_profile(character, level=1, ascension=0):
    """Elemento, arquétipo e atributos da carta, para exibir ao jogador."""
    element = ELEMENTS[character["element"]]
    archetype = ARCHETYPES[character["archetype"]]
    return {
        "element": character["element"],
        "elementLabel": element["label"],
        "strongAgainst": list(element["strong_against"]),
        "archetype": character["archetype"],
        "archetypeLabel": archetype["label"],
        "archetypeDescription": archetype["description"],
        "stats": battle_stats(character, level, ascension),
    }
