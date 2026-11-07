"""Ascensão: cópias repetidas fortalecem a carta.

O jogador consome cópias extras de uma carta para subir a ascensão dela. A
ascensão é do jogador (fica em `CardAscensionsTable`, por jogador e carta), não
de uma cópia: vale para todas as cópias que ele tiver e continua salva mesmo
que ele venda as que sobraram. Quem compra uma cópia no mercado recebe a carta
sem ascensão.

- Cada nível de ascensão aumenta os atributos grandes (vitality, might,
  arcana, bulwark, resolve) em ASCENSION_STAT_BONUS.
- Na ascensão SKILL_UNLOCK_ASCENSION a carta aprende mais uma habilidade do
  arquétipo (até o máximo do arquétipo), então uma 3★ chega a 2 habilidades e
  uma 4★ chega à suprema.
- Subir sempre deixa pelo menos uma cópia na coleção.

Tudo aqui é regra do jogo e fica SÓ no backend.
"""

MAX_ASCENSION = 3

# Cópias consumidas para chegar a cada nível (além da que fica na coleção).
ASCENSION_COSTS = {1: 1, 2: 2, 3: 3}

ASCENSION_STAT_BONUS = 0.05

SKILL_UNLOCK_ASCENSION = 3


def clamp_ascension(value):
    """Ascensão válida (0..MAX_ASCENSION) a partir de um valor salvo."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_ASCENSION, value))


def next_ascension_cost(ascension):
    """Cópias consumidas para subir de `ascension`, ou None se já está no máximo."""
    return ASCENSION_COSTS.get(clamp_ascension(ascension) + 1)


def stat_multiplier(ascension):
    return 1 + ASCENSION_STAT_BONUS * clamp_ascension(ascension)


def bonus_skills(ascension):
    """Habilidades extras do arquétipo liberadas pela ascensão."""
    return 1 if clamp_ascension(ascension) >= SKILL_UNLOCK_ASCENSION else 0


def can_ascend(ascension, quantity):
    """Se `quantity` cópias bastam para subir (sempre sobra uma)."""
    cost = next_ascension_cost(ascension)
    return cost is not None and quantity >= cost + 1


def public_ascension(ascension, quantity, unlocks_skill):
    """Ascensão da carta para exibir ao jogador.

    `unlocks_skill`: se chegar a SKILL_UNLOCK_ASCENSION dá uma habilidade
    nova a esta carta (depende da raridade e do arquétipo, calculado em
    `battle`).
    """
    ascension = clamp_ascension(ascension)
    cost = next_ascension_cost(ascension)
    return {
        "level": ascension,
        "max": MAX_ASCENSION,
        "statBonusPercent": round(ASCENSION_STAT_BONUS * ascension * 100),
        "nextCost": cost,
        "nextStatBonusPercent": (
            round(ASCENSION_STAT_BONUS * (ascension + 1) * 100) if cost else None
        ),
        "canAscend": can_ascend(ascension, quantity),
        "skillUnlockLevel": SKILL_UNLOCK_ASCENSION,
        "unlocksSkill": unlocks_skill,
    }


def read_ascensions(client, table_name, user_id):
    """{file_name: ascensão} do jogador (cliente de baixo nível do boto3)."""
    ascensions = {}
    query_kwargs = {
        "TableName": table_name,
        "KeyConditionExpression": "userId = :userId",
        "ExpressionAttributeValues": {":userId": {"S": user_id}},
        "ConsistentRead": True,
    }
    while True:
        result = client.query(**query_kwargs)
        for item in result.get("Items", []):
            file_name = item.get("file_name", {}).get("S")
            if file_name:
                ascensions[file_name] = clamp_ascension(
                    item.get("ascension", {}).get("N", "0")
                )
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return ascensions
        query_kwargs["ExclusiveStartKey"] = last_key
