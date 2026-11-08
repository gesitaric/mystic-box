"""Coleção por região: ter todos os personagens de uma região paga uma recompensa.

- A recompensa é única por região (COLLECTION_REWARD_PER_CHAMPION por
  personagem da região) e o jogador precisa pedir para receber.
- O servidor confere a coleção na hora do pedido. Vender cartas depois não
  desfaz o que já foi recebido.
- Quem recebeu fica marcado em RegionProgressTable (`claimed_<região>`), o
  mesmo item do progresso da campanha.
"""

from .lore import REGIONS, STORIES

COLLECTION_REWARD_PER_CHAMPION = 40
CLAIM_ATTRIBUTE_PREFIX = "claimed_"

_REGION_NAMES = {region["id"]: region["name"] for region in REGIONS}


def residents(region_id):
    """file_names dos personagens que vêm da região."""
    return sorted(name for name, lore in STORIES.items() if lore["region"] == region_id)


def regions_with_residents():
    return [region["id"] for region in REGIONS if residents(region["id"])]


def collection_reward(region_id):
    return len(residents(region_id)) * COLLECTION_REWARD_PER_CHAMPION


def claim_attribute(region_id):
    return f"{CLAIM_ATTRIBUTE_PREFIX}{region_id}"


def claimed_from_item(item):
    """Regiões cuja recompensa de coleção o jogador já recebeu."""
    return {
        region_id
        for region_id in regions_with_residents()
        if claim_attribute(region_id) in (item or {})
    }


def is_complete(region_id, owned):
    names = residents(region_id)
    return bool(names) and all(name in owned for name in names)


def public_collection(owned, claimed):
    """Quantos personagens de cada região o jogador tem e o que a coleção paga."""
    return [
        {
            "region": region_id,
            "regionName": _REGION_NAMES[region_id],
            "owned": sum(1 for name in residents(region_id) if name in owned),
            "total": len(residents(region_id)),
            "complete": is_complete(region_id, owned),
            "claimed": region_id in claimed,
            "reward": collection_reward(region_id),
        }
        for region_id in regions_with_residents()
    ]
