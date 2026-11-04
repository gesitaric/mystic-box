"""Nível e experiência do jogador.

O servidor guarda só a experiência total (`experience`) em UserProgressTable;
o nível é sempre calculado a partir dela com as regras abaixo. Subir de nível
dá Fragmentos Arcanos de recompensa.
"""

MAX_LEVEL = 50

# Experiência para ir do nível N para o N+1.
BASE_LEVEL_EXPERIENCE = 100
LEVEL_EXPERIENCE_STEP = 30

# Fragmentos Arcanos ganhos ao alcançar o nível N: N * LEVEL_UP_SHARDS_PER_LEVEL.
LEVEL_UP_SHARDS_PER_LEVEL = 10


def experience_to_next(level):
    """Experiência necessária para sair de `level` e chegar ao próximo."""
    if level >= MAX_LEVEL:
        return None
    return BASE_LEVEL_EXPERIENCE + LEVEL_EXPERIENCE_STEP * (level - 1)


def level_for_experience(experience):
    """(nível, experiência dentro do nível) para uma experiência total."""
    level = 1
    remaining = max(0, int(experience))
    while level < MAX_LEVEL:
        needed = experience_to_next(level)
        if remaining < needed:
            break
        remaining -= needed
        level += 1
    return level, remaining


def level_up_reward(old_level, new_level):
    """Fragmentos Arcanos ganhos por todos os níveis alcançados entre os dois."""
    return sum(
        level * LEVEL_UP_SHARDS_PER_LEVEL for level in range(old_level + 1, new_level + 1)
    )


def public_progress(experience, wins=0, losses=0):
    """Nível e progresso do jogador, para exibir."""
    level, into_level = level_for_experience(experience)
    return {
        "level": level,
        "maxLevel": MAX_LEVEL,
        "experience": int(experience),
        "levelExperience": into_level,
        "nextLevelExperience": experience_to_next(level),
        "wins": int(wins),
        "losses": int(losses),
    }
