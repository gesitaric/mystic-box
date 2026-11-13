"""Relíquias: itens de cada região que a personagem equipa para a batalha.

- Cada região da campanha tem uma relíquia (RELICS). O efeito sempre tem uma
  troca: atributos que sobem (`bonuses`) e atributos que descem (`penalties`),
  em fração do atributo.
- Sintonia: equipada numa personagem da mesma região da relíquia, os bônus
  são multiplicados por ATTUNED_BONUS_MULTIPLIER (as perdas não) e a relíquia
  desperta (`awakening`) no começo da batalha.
- Cada personagem leva no máximo uma relíquia. O equipamento é do jogador e
  da personagem, como a ascensão (`CardRelicsTable`, por jogador e carta):
  continua salvo se ele vender as cópias da carta.
- Como conseguir: a primeira vitória sobre o chefe de uma região dá a
  relíquia dela; depois, o jogador forja mais cópias com Fragmentos Arcanos
  (FORGE_COST), só das regiões cujo chefe já venceu, até MAX_COPIES.
- As cópias ficam em `UserRelicsTable` (por jogador e relíquia, com `owned` e
  `equipped`). Equipar só passa se `equipped < owned`.

Tudo aqui é regra do jogo e fica SÓ no backend.
"""

from .cards import get_character
from .lore import REGIONS, region_of

FORGE_COST = 250
MAX_COPIES = 5
ATTUNED_BONUS_MULTIPLIER = 1.5

# Efeitos do despertar (só com sintonia), no começo da batalha:
#   ("status", status, turnos[, fração da vitalidade máx. para o escudo])
#   ("aether", quantidade) para o time.
RELICS = {
    "frostgate-pennant": {
        "region": "hrimvald",
        "name": "Frostgate Pennant",
        "lore": "The banner the knights of the pass raise when the wind-wolves howl. "
                "It has never been lowered, only frozen in place.",
        "bonuses": {"bulwark": 0.12, "resolve": 0.10},
        "penalties": {"celerity": 0.10},
        "awakening": ("status", "shield", 3, 0.15),
        "awakeningText": "Starts with a shield worth 15% of max vitality.",
    },
    "windcaller-compass": {
        "region": "zephyrine",
        "name": "Windcaller's Compass",
        "lore": "Its needle points wherever the empress wants the isles to go. "
                "Nobody else has ever made it move.",
        "bonuses": {"celerity": 0.15},
        "penalties": {"vitality": 0.08},
        "awakening": ("aether", 1),
        "awakeningText": "The team starts with +1 Aether.",
    },
    "gravebloom-lantern": {
        "region": "nocthaven",
        "name": "Gravebloom Lantern",
        "lore": "A lantern lit with the flowers that grow on Nocthaven's graves. "
                "Its light makes shadows step back, and sometimes bow.",
        "bonuses": {"arcana": 0.14},
        "penalties": {"vitality": 0.08},
        "awakening": ("status", "guard", 1),
        "awakeningText": "Starts Guarded until its first turn.",
    },
    "fallen-star-shard": {
        "region": "skyspire",
        "name": "Fallen Star Shard",
        "lore": "A splinter of a star that fell through the cracked sky. "
                "The astrologers swear it still remembers where it came from.",
        "bonuses": {"fate": 0.40, "arcana": 0.06},
        "penalties": {"bulwark": 0.08},
        "awakening": ("status", "empower", 2),
        "awakeningText": "Starts Empowered for 2 turns.",
    },
    "hearthstone-charm": {
        "region": "greenhollow",
        "name": "Hearthstone Charm",
        "lore": "A smooth stone from a farmhouse hearth, still warm years later. "
                "Every child of the vale carries one when they leave home.",
        "bonuses": {"vitality": 0.14},
        "penalties": {"might": 0.08},
        "awakening": ("status", "regen", 3),
        "awakeningText": "Starts with Regen for 3 turns.",
    },
    "moonbloom-circlet": {
        "region": "sylvaran",
        "name": "Moonbloom Circlet",
        "lore": "Woven from moon flowers that only open for those the forest trusts. "
                "It wilts on anyone who lies.",
        "bonuses": {"resolve": 0.12, "arcana": 0.06},
        "penalties": {"might": 0.08},
        "awakening": ("status", "regen", 2),
        "awakeningText": "Starts with Regen for 2 turns.",
    },
    "sunsworn-aegis": {
        "region": "aurelian",
        "name": "Sunsworn Aegis",
        "lore": "The shield of the knight who held the Dominion's gates shut. "
                "It is heavy with everything that knight could not save.",
        "bonuses": {"bulwark": 0.15},
        "penalties": {"celerity": 0.08},
        "awakening": ("status", "taunt", 2),
        "awakeningText": "Starts with Taunt for 2 turns.",
    },
    "petalfall-tsuba": {
        "region": "hoshigane",
        "name": "Petalfall Tsuba",
        "lore": "A sword guard carved with falling petals. Its clan says a blade "
                "that wears it never strikes twice, because it never needs to.",
        "bonuses": {"might": 0.12, "fate": 0.25},
        "penalties": {"vitality": 0.10},
        "awakening": ("status", "empower", 2),
        "awakeningText": "Starts Empowered for 2 turns.",
    },
    "smugglers-signet": {
        "region": "spirehollow",
        "name": "Smuggler's Signet",
        "lore": "A ring that opens every back door in Spirehollow. "
                "Its last three owners all left town in a hurry.",
        "bonuses": {"celerity": 0.12, "fate": 0.25},
        "penalties": {"bulwark": 0.10},
        "awakening": ("status", "guard", 1),
        "awakeningText": "Starts Guarded until its first turn.",
    },
    "clanbreaker-torc": {
        "region": "ironfang",
        "name": "Clanbreaker Torc",
        "lore": "An iron collar taken from the chief of a rival clan. "
                "Wearing it is an insult to half the highlands.",
        "bonuses": {"might": 0.15},
        "penalties": {"resolve": 0.10},
        "awakening": ("status", "empower", 1),
        "awakeningText": "Starts Empowered for 1 turn.",
    },
    "drowned-bell": {
        "region": "thalassar",
        "name": "Drowned Bell",
        "lore": "A small bell from a sunken temple. Underwater it rings on its own; "
                "on land it only rings for those about to fall.",
        "bonuses": {"resolve": 0.14},
        "penalties": {"celerity": 0.08},
        "awakening": ("status", "shield", 3, 0.12),
        "awakeningText": "Starts with a shield worth 12% of max vitality.",
    },
    "everfire-ember": {
        "region": "cinderpeak",
        "name": "Everfire Ember",
        "lore": "A spark of the Everfire kept in black glass. "
                "The dragons of Cinderpeak can smell it from a mountain away.",
        "bonuses": {"might": 0.08, "arcana": 0.08},
        "penalties": {"resolve": 0.10},
        "awakening": ("aether", 1),
        "awakeningText": "The team starts with +1 Aether.",
    },
    "overclocked-coil": {
        "region": "cogsreach",
        "name": "Overclocked Coil",
        "lore": "A coil of captured lightning that a baron swore could not be built. "
                "It hums a little too fast, and a little too hot.",
        "bonuses": {"celerity": 0.10, "arcana": 0.08},
        "penalties": {"vitality": 0.10},
        "awakening": ("aether", 1),
        "awakeningText": "The team starts with +1 Aether.",
    },
}

_REGION_NAMES = {region["id"]: region["name"] for region in REGIONS}
_BY_REGION = {relic["region"]: relic_id for relic_id, relic in RELICS.items()}

_STAT_LABELS = {
    "vitality": "Vitality",
    "might": "Might",
    "arcana": "Arcana",
    "bulwark": "Bulwark",
    "resolve": "Resolve",
    "celerity": "Celerity",
    "fate": "Fate",
}


def get_relic(relic_id):
    """Definição da relíquia, ou None."""
    return RELICS.get(relic_id) if isinstance(relic_id, str) else None


def relic_for_region(region_id):
    """Id da relíquia da região, ou None."""
    return _BY_REGION.get(region_id)


def is_attuned(relic_id, file_name):
    """Se a relíquia é da mesma região da personagem."""
    relic = get_relic(relic_id)
    return bool(relic) and region_of(file_name) == relic["region"]


def stat_changes(relic_id, file_name):
    """{atributo: fração} que a relíquia aplica nessa personagem (perdas negativas)."""
    relic = get_relic(relic_id)
    if not relic:
        return {}
    bonus = ATTUNED_BONUS_MULTIPLIER if is_attuned(relic_id, file_name) else 1
    changes = {stat: value * bonus for stat, value in relic["bonuses"].items()}
    for stat, value in relic["penalties"].items():
        changes[stat] = changes.get(stat, 0) - value
    return changes


def apply_relic(stats, relic_id, file_name):
    """Aplica a relíquia nos atributos (mexe em `stats`)."""
    for stat, change in stat_changes(relic_id, file_name).items():
        stats[stat] = max(1, round(stats[stat] * (1 + change)))
    return stats


def awakening(relic_id, file_name):
    """Efeito do despertar (só com sintonia), ou None."""
    if not is_attuned(relic_id, file_name):
        return None
    return RELICS[relic_id]["awakening"]


def _percent(value):
    return round(value * 100)


def _changes(values, multiplier=1):
    return [
        {"stat": stat, "label": _STAT_LABELS[stat], "percent": _percent(value * multiplier)}
        for stat, value in values.items()
    ]


def public_relic(relic_id):
    """Relíquia para exibir (efeito comum e com sintonia)."""
    relic = RELICS[relic_id]
    return {
        "id": relic_id,
        "name": relic["name"],
        "lore": relic["lore"],
        "region": relic["region"],
        "regionName": _REGION_NAMES[relic["region"]],
        "bonuses": _changes(relic["bonuses"]),
        "penalties": _changes(relic["penalties"]),
        "attunedBonuses": _changes(relic["bonuses"], ATTUNED_BONUS_MULTIPLIER),
        "awakening": relic["awakeningText"],
    }


def public_equipped(relic_id, file_name):
    """Relíquia equipada numa personagem, com a sintonia já decidida, ou None."""
    if not get_relic(relic_id):
        return None
    attuned = is_attuned(relic_id, file_name)
    relic = RELICS[relic_id]
    return {
        "id": relic_id,
        "name": relic["name"],
        "region": relic["region"],
        "attuned": attuned,
        "changes": [
            {"stat": stat, "label": _STAT_LABELS[stat], "percent": _percent(change)}
            for stat, change in stat_changes(relic_id, file_name).items()
        ],
        "awakening": relic["awakeningText"] if attuned else None,
    }


def public_inventory(owned, equipped_on, unlocked_regions, balance, for_card=None):
    """Todas as relíquias com o que o jogador tem e pode fazer.

    `owned`: {relicId: {"owned": n, "equipped": n}}.
    `equipped_on`: {file_name: relicId}.
    `unlocked_regions`: regiões cujo chefe o jogador já venceu.
    `for_card`: file_name de uma personagem; cada relíquia traz em `forCard` o
    efeito nela (com a sintonia já decidida).
    """
    relics = []
    for relic_id, relic in RELICS.items():
        counts = owned.get(relic_id, {})
        count = counts.get("owned", 0)
        unlocked = relic["region"] in unlocked_regions
        wearers = sorted(
            (
                {"fileName": name, "name": get_character(name)["name"],
                 "attuned": is_attuned(relic_id, name)}
                for name, worn in equipped_on.items()
                if worn == relic_id and get_character(name)
            ),
            key=lambda wearer: wearer["name"],
        )
        relics.append(
            {
                **public_relic(relic_id),
                "owned": count,
                "equipped": len(wearers),
                "free": max(0, count - counts.get("equipped", 0)),
                "equippedOn": wearers,
                "unlocked": unlocked,
                "canForge": unlocked and count < MAX_COPIES and balance >= FORGE_COST,
                "forCard": public_equipped(relic_id, for_card) if for_card else None,
            }
        )
    return relics


def public_rules():
    return {
        "forgeCost": FORGE_COST,
        "maxCopies": MAX_COPIES,
        "perCharacter": 1,
        "attunedBonusPercent": _percent(ATTUNED_BONUS_MULTIPLIER - 1),
        "relics": [public_relic(relic_id) for relic_id in RELICS],
    }


def read_equipped(client, table_name, user_id):
    """{file_name: relicId} do jogador (cliente de baixo nível do boto3)."""
    equipped = {}
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
            relic_id = item.get("relicId", {}).get("S")
            if file_name and get_relic(relic_id):
                equipped[file_name] = relic_id
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return equipped
        query_kwargs["ExclusiveStartKey"] = last_key


def read_owned(client, table_name, user_id):
    """{relicId: {"owned": n, "equipped": n}} do jogador."""
    owned = {}
    query_kwargs = {
        "TableName": table_name,
        "KeyConditionExpression": "userId = :userId",
        "ExpressionAttributeValues": {":userId": {"S": user_id}},
        "ConsistentRead": True,
    }
    while True:
        result = client.query(**query_kwargs)
        for item in result.get("Items", []):
            relic_id = item.get("relicId", {}).get("S")
            if get_relic(relic_id):
                owned[relic_id] = {
                    "owned": int(float(item.get("owned", {}).get("N", "0"))),
                    "equipped": int(float(item.get("equipped", {}).get("N", "0"))),
                }
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return owned
        query_kwargs["ExclusiveStartKey"] = last_key


def grant_update(table_name, user_id, relic_id):
    """Item de transação que dá uma cópia da relíquia (cria `equipped` = 0)."""
    return {
        "Update": {
            "TableName": table_name,
            "Key": {"userId": {"S": user_id}, "relicId": {"S": relic_id}},
            "UpdateExpression": "ADD owned :one, equipped :zero",
            "ExpressionAttributeValues": {":one": {"N": "1"}, ":zero": {"N": "0"}},
        }
    }
