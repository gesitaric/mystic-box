"""Regras do jogo explicadas ao jogador (tela de ajuda / Grimório).

Monta, a partir das constantes de `cards.py`, `stats.py`, `battle.py`,
`pvp.py`, `progression.py` e `ascension.py`, tudo que a tela de regras mostra: chances do sorteio,
limites do mercado, curva de nível e as regras da batalha. Nada aqui é copiado: mudar uma
regra nesses módulos muda o que o jogador lê.
"""

from . import ascension, battle, cards, progression, pvp, stats

RARITIES = (5, 4, 3)


def _percent(value):
    return round(value * 100, 1)


def rarity_chances(weights_by_card):
    """Chance (%) de cada raridade quando cada carta tem o peso da sua raridade."""
    counts = {rarity: 0 for rarity in RARITIES}
    for character in cards.CHARACTERS:
        counts[character["rarity"]] += 1
    total = sum(weights_by_card[rarity] * counts[rarity] for rarity in RARITIES)
    return [
        {
            "rarity": rarity,
            "cardCount": counts[rarity],
            "chance": _percent(weights_by_card[rarity] * counts[rarity] / total),
        }
        for rarity in RARITIES
    ]


def _shop_rules():
    return {
        "maxListingQuantity": cards.MAX_LISTING_QUANTITY,
        "maxActiveListings": cards.MAX_ACTIVE_LISTINGS,
        "listingPrices": [
            {"rarity": rarity, **cards.LISTING_PRICE_LIMITS[rarity]}
            for rarity in RARITIES
        ],
    }


def _progression_rules():
    sample_levels = [1, 2, 5, 10, 20, progression.MAX_LEVEL - 1]
    return {
        "maxLevel": progression.MAX_LEVEL,
        "baseLevelExperience": progression.BASE_LEVEL_EXPERIENCE,
        "levelExperienceStep": progression.LEVEL_EXPERIENCE_STEP,
        "levelUpShardsPerLevel": progression.LEVEL_UP_SHARDS_PER_LEVEL,
        "levelStatBonusPercent": _percent(stats.LEVEL_STAT_BONUS),
        "examples": [
            {
                "level": level,
                "experienceToNext": progression.experience_to_next(level),
                "shardsOnReach": (level + 1) * progression.LEVEL_UP_SHARDS_PER_LEVEL,
            }
            for level in sample_levels
        ],
    }


def _archetype_rules():
    archetypes = []
    for key, archetype in stats.ARCHETYPES.items():
        skills = []
        for index, skill_id in enumerate(battle.ARCHETYPE_SKILLS[key]):
            unlock = next(
                r for r in sorted(RARITIES) if battle.archetype_skill_count(r) > index
            )
            skills.append(
                {
                    **battle.public_skill(skill_id),
                    "unlockRarity": unlock,
                    "supreme": index == len(battle.ARCHETYPE_SKILLS[key]) - 1,
                }
            )
        archetypes.append(
            {
                "id": key,
                "label": archetype["label"],
                "description": archetype["description"],
                "baseStats": dict(archetype["base"]),
                "skills": skills,
            }
        )
    return archetypes


def _difficulty_rules():
    result = []
    for key, difficulty in battle.DIFFICULTIES.items():
        weights = difficulty["rarityWeights"]
        total = sum(weights.values())
        result.append(
            {
                "id": key,
                "label": difficulty["label"],
                "description": difficulty["description"],
                "minLevel": difficulty["minLevel"],
                "levelOffset": difficulty["levelOffset"],
                "enemyPowerPercent": _percent(difficulty["enemyPower"]),
                "rarityChances": [
                    {"rarity": r, "chance": _percent(weights[r] / total)} for r in RARITIES
                ],
                "winExperience": difficulty["experience"],
                "lossExperience": round(difficulty["experience"] * battle.LOSS_EXPERIENCE_RATIO),
            }
        )
    return result


def _battle_rules():
    return {
        "teamSize": battle.TEAM_SIZE,
        "maxRounds": battle.MAX_ROUNDS,
        "aether": {
            "starting": battle.STARTING_AETHER,
            "max": battle.MAX_AETHER,
            "perTurn": battle.AETHER_PER_TURN,
            "basicSkillBonus": battle.BASIC_SKILL_AETHER,
        },
        "damage": {
            "defenseConstant": battle.DEFENSE_CONSTANT,
            "variancePercent": _percent(battle.DAMAGE_VARIANCE),
            "criticalMultiplier": battle.CRIT_MULTIPLIER,
            "hybridPowerPercent": _percent(battle.HYBRID_POWER_RATIO),
            "maxFate": stats.MAX_FATE,
        },
        "stats": [
            {"id": key, "label": stats.STAT_LABELS[key], "description": stats.STAT_DESCRIPTIONS[key]}
            for key in stats.STAT_KEYS
        ],
        "rarityScaling": [
            {
                "rarity": rarity,
                "statMultiplier": stats.RARITY_SCALE[rarity],
                "celerityBonus": stats.RARITY_CELERITY_BONUS[rarity],
                "fateBonus": stats.RARITY_FATE_BONUS[rarity],
                "archetypeSkills": battle.archetype_skill_count(rarity),
            }
            for rarity in RARITIES
        ],
        "elements": {
            "advantageMultiplier": stats.ADVANTAGE_MULTIPLIER,
            "disadvantageMultiplier": stats.DISADVANTAGE_MULTIPLIER,
            "list": [
                {
                    "id": key,
                    "label": element["label"],
                    "strongAgainst": list(element["strong_against"]),
                    "weakAgainst": [
                        other for other, data in stats.ELEMENTS.items()
                        if key in data["strong_against"]
                        and stats.element_multiplier(key, other) < 1
                    ],
                    "rider": battle.ELEMENT_RIDERS[key],
                }
                for key, element in stats.ELEMENTS.items()
            ],
        },
        "basicSkills": [battle.public_skill(s) for s in battle.BASIC_SKILLS],
        "archetypes": _archetype_rules(),
        "statuses": [
            {"id": key, "label": s["label"], "kind": s["kind"], "description": s["description"]}
            for key, s in battle.STATUSES.items()
        ],
        "difficulties": _difficulty_rules(),
        "bonds": {
            "statBonusPercent": _percent(battle.BOND_STAT_BONUS),
            "griefStatus": battle.STATUSES["empower"]["label"],
            "griefTurns": battle.BOND_GRIEF_TURNS,
            "rivalDamagePercent": _percent(battle.RIVAL_DAMAGE_MULTIPLIER - 1),
        },
        "rewards": {
            "lossExperiencePercent": _percent(battle.LOSS_EXPERIENCE_RATIO),
            "lossExperiencePerDefeat": battle.LOSS_EXPERIENCE_PER_DEFEAT,
            "forfeitExperience": 0,
        },
    }


def _ascension_rules():
    return {
        "maxLevel": ascension.MAX_ASCENSION,
        "statBonusPercent": _percent(ascension.ASCENSION_STAT_BONUS),
        "skillUnlockLevel": ascension.SKILL_UNLOCK_ASCENSION,
        "levels": [
            {
                "level": level,
                "copies": cost,
                "statBonusPercent": _percent(ascension.ASCENSION_STAT_BONUS * level),
                "unlocksSkill": level == ascension.SKILL_UNLOCK_ASCENSION,
            }
            for level, cost in sorted(ascension.ASCENSION_COSTS.items())
        ],
        "skillsByRarity": [
            {
                "rarity": rarity,
                "base": battle.archetype_skill_count(rarity),
                "ascended": battle.archetype_skill_count(rarity, ascension.MAX_ASCENSION),
            }
            for rarity in RARITIES
        ],
    }


def public_rules(cooldown_seconds, token_ttl_seconds):
    """Todas as regras que o jogador pode consultar, com os valores atuais."""
    return {
        "summon": {
            "cardsPerSummon": cards.SUMMON_SIZE,
            "cooldownSeconds": cooldown_seconds,
            "tokenTtlSeconds": token_ttl_seconds,
            "rarityChances": rarity_chances(cards.RARITY_WEIGHTS),
            "lastCardRarityChances": rarity_chances(cards.LAST_CARD_RARITY_WEIGHTS),
            "totalCards": len(cards.CHARACTERS),
        },
        "shop": _shop_rules(),
        "progression": _progression_rules(),
        "battle": _battle_rules(),
        "ascension": _ascension_rules(),
        "pvp": pvp.public_rules(),
    }
