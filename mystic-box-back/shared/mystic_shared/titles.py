"""Títulos de perfil: conquistas tiradas da história, mostradas aos outros jogadores.

Cada título tem uma condição, sempre conferida no servidor:
- ("level", n): chegar ao nível n.
- ("collection", região): receber a recompensa da coleção da região.
- ("campaign", região): vencer o chefe da campanha da região.
- ("secret", file_name): liberar o capítulo secreto da carta (ascensão).

Todas as condições só crescem (nível, coleção recebida, fases vencidas e
ascensão não voltam atrás), então um título conquistado não se perde. O
jogador escolhe um título (ou nenhum) e ele aparece no perfil, na busca de
jogadores e no duelo online.
"""

from .ascension import read_ascensions
from .campaign import CAMPAIGN, progress_from_item
from .lore import REGIONS, SECRET_UNLOCK_ASCENSION, SECRETS
from .mastery import claimed_from_item
from .progression import level_for_experience

_REGION_NAMES = {region["id"]: region["name"] for region in REGIONS}

# (título da coleção completa, título de vencer o chefe da campanha)
REGION_TITLES = {
    "hrimvald": ("Friend of the Wind-Wolves", "Breaker of the Frostgate"),
    "zephyrine": ("Sky Guard of Zephyrine", "Rider of the Drifting Throne"),
    "nocthaven": ("Lantern-Keeper of Nocthaven", "Who Faced the Last Warden"),
    "skyspire": ("Stargazer of Skyspire", "Catcher of Falling Stars"),
    "greenhollow": ("Neighbor of Greenhollow", "Who Ate Grizelda's Cake"),
    "sylvaran": ("Child of the Grove", "Who Heard the Second Heart"),
    "aurelian": ("Knight of the Lion's Gate", "Who Held Both Gates"),
    "hoshigane": ("Student of the Petal", "Twin Petal Duelist"),
    "spirehollow": ("Rooftop Runner", "Breaker of the Masked Contract"),
    "ironfang": ("Blood-Brother of the Clans", "Who Saw Gorvane Rise"),
    "thalassar": ("Tidewatch Sentinel", "Who Heard the Tide-Witch's Song"),
    "cinderpeak": ("Ember-Touched", "Who Walked into the Everfire"),
    "cogsreach": ("Honorary Inventor", "Accomplice of the Tenth Robbery"),
}

# Títulos de capítulos secretos marcantes: (id, nome, carta).
SECRET_TITLES = [
    ("who_freed_lira", "Who Freed Lira", "ravenna.png"),
    ("everfire_keeper", "Keeper of the Everfire", "ignis.jfif"),
    ("kages_secret", "Who Learned Kage's Secret", "kage.jfif"),
    ("last_seed", "Guardian of the Last Seed", "verdana.jfif"),
    ("bearer_of_the_key", "Bearer of the Key", "uriel.jfif"),
    ("mapper_of_the_lid", "Mapper of the Lid", "astra.jfif"),
    ("corins_name", "Who Knew Corin's Name", "corvus.jfif"),
    ("seventh_warden", "Friend of the Seventh Warden", "grizelda.jfif"),
]


def _build_titles():
    titles = [
        {"id": "summoner", "name": "Summoner",
         "description": "Answer the Box's call.", "condition": ("level", 1)},
        {"id": "arcane_adept", "name": "Arcane Adept",
         "description": "Reach level 10.", "condition": ("level", 10)},
        {"id": "archsummoner", "name": "Archsummoner",
         "description": "Reach level 25.", "condition": ("level", 25)},
    ]
    for region_id in CAMPAIGN:
        collection_name, campaign_name = REGION_TITLES[region_id]
        region_name = _REGION_NAMES[region_id]
        titles.append({
            "id": f"collection_{region_id}", "name": collection_name,
            "description": f"Summon every champion of {region_name} and claim the reward.",
            "condition": ("collection", region_id),
        })
        titles.append({
            "id": f"campaign_{region_id}", "name": campaign_name,
            "description": f"Defeat the champion of {region_name} in the campaign.",
            "condition": ("campaign", region_id),
        })
    for title_id, name, file_name in SECRET_TITLES:
        titles.append({
            "id": title_id, "name": name,
            "description": f"Unlock the secret chapter \"{SECRETS[file_name][0]}\".",
            "condition": ("secret", file_name),
        })
    return titles


TITLES = _build_titles()
_BY_ID = {title["id"]: title for title in TITLES}


def get_title(title_id):
    return _BY_ID.get(title_id)


def title_name(title_id):
    title = _BY_ID.get(title_id)
    return title["name"] if title else None


def earned_titles(level, campaign_progress, claimed, ascensions):
    """Ids dos títulos conquistados.

    `campaign_progress`: {região: fases vencidas}; `claimed`: regiões com a
    coleção recebida; `ascensions`: {file_name: ascensão}.
    """
    earned = set()
    for title in TITLES:
        kind, value = title["condition"]
        if kind == "level":
            ok = level >= value
        elif kind == "collection":
            ok = value in claimed
        elif kind == "campaign":
            ok = campaign_progress.get(value, 0) >= len(CAMPAIGN[value]["stages"])
        else:
            ok = ascensions.get(value, 0) >= SECRET_UNLOCK_ASCENSION
        if ok:
            earned.add(title["id"])
    return earned


def public_titles(earned):
    return [
        {"id": t["id"], "name": t["name"], "description": t["description"],
         "earned": t["id"] in earned}
        for t in TITLES
    ]


def load_earned_titles(client, user_id, progress_table, region_table, ascensions_table):
    """Lê no banco o que o jogador conquistou e devolve (nível, títulos conquistados)."""
    def get(table):
        return client.get_item(
            TableName=table, Key={"userId": {"S": user_id}}, ConsistentRead=True
        ).get("Item") or {}

    progress = get(progress_table)
    level, _ = level_for_experience(int(progress.get("experience", {}).get("N", "0")))
    region_item = get(region_table)
    earned = earned_titles(
        level,
        progress_from_item(region_item),
        claimed_from_item(region_item),
        read_ascensions(client, ascensions_table, user_id),
    )
    return level, earned
