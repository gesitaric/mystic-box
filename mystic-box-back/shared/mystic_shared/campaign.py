"""Campanha pelo mapa: cada região é uma série de batalhas com um chefe no fim.

- Cada região com personagens tem STAGES_PER_REGION fases. A fase N só abre
  depois de vencer a N-1; a última é o chefe.
- Os inimigos de cada fase são fixos (personagens da região e convidados com
  laço ou rivalidade). Nível, força, experiência e recompensa saem de
  STAGE_RULES (por posição da fase).
- A primeira vitória em cada fase paga a recompensa em Fragmentos Arcanos.
  Repetir uma fase vencida dá só experiência.
- Vencer o chefe revela o epílogo da região.

O progresso fica num item por jogador em RegionProgressTable, com um
atributo `stage_<região>` (fases vencidas). Nada disso vem do cliente.
"""

from .cards import get_character
from .lore import REGIONS
from .progression import MAX_LEVEL

STAGES_PER_REGION = 3

# Por posição da fase (0 = primeira): diferença de nível dos inimigos para o
# jogador, multiplicador dos atributos, experiência da vitória e recompensa
# da primeira vitória.
STAGE_RULES = [
    {"levelOffset": -1, "power": 0.85, "experience": 50, "reward": 30},
    {"levelOffset": 0, "power": 0.95, "experience": 70, "reward": 50},
    {"levelOffset": 2, "power": 1.05, "experience": 110, "reward": 100},
]

STAGE_ATTRIBUTE_PREFIX = "stage_"


def _stage(name, intro, *enemies):
    return {"name": name, "intro": intro, "enemies": list(enemies)}


CAMPAIGN = {
    "hrimvald": {
        "stages": [
            _stage("Wolf Tracks",
                   "Fenric's hunting party mistakes you for poachers in the northern snow.",
                   "fenric.jfif", "tavik.jfif", "verdana.jfif"),
            _stage("The Frozen Lake",
                   "Glacius guards the lake where Hrimfang's old pack sleeps under the ice.",
                   "glacius.jfif", "fenric.jfif", "tavik.jfif"),
            _stage("The Knight of the Frostgate",
                   "Boreas stands at the Frostgate with her squire and the lost son of the pack.",
                   "boreas.jfif", "glacius.jfif", "fenric.jfif"),
        ],
        "epilogue": "Boreas lowers her blade and looks at Fenric for a long time. \"The wind "
                    "will need a leader,\" she says. Nobody understands her. Not yet.",
    },
    "zephyrine": {
        "stages": [
            _stage("Sky Guard Patrol",
                   "A patrol of the sky guard intercepts your airship, with two stowaways "
                   "from Cogsreach on board.",
                   "kyrielle.jfif", "dorian.jfif", "brina.jfif"),
            _stage("The Sovereign's Citadel",
                   "Draemir receives you in his citadel, with his niece and the boy from the "
                   "burning mountain.",
                   "draemir.jfif", "drakara.jfif", "pyralis.jfif"),
            _stage("The Drifting Throne",
                   "The empress herself takes the field, flanked by her captain and the "
                   "oldest dragon in the sky.",
                   "vaelora.jfif", "kyrielle.jfif", "draemir.jfif"),
        ],
        "epilogue": "Vaelora laughs as she yields, and only then do you see how tired she is. "
                    "The isles drift one more inch toward the Riftheart.",
    },
    "nocthaven": {
        "stages": [
            _stage("The Crypt Gates",
                   "The keepers of the crypts do not let strangers pass, least of all "
                   "strangers who carry the Box's mark.",
                   "morwen.jfif", "nocturna.jfif", "amethia.jfif"),
            _stage("The Shadow Court",
                   "Zarathor's court gathers: the tyrant, his assassin and the widow sworn "
                   "to kill him, side by side for one night.",
                   "zarathor.jfif", "vesper.jfif", "morwen.jfif"),
            _stage("The Last Warden",
                   "In the high tower, Malachar closes his tome. His jester laughs. A raven "
                   "of violet fire watches from the window.",
                   "malachar.jfif", "mortis.jfif", "ravenna.png"),
        ],
        "epilogue": "The raven of violet fire lands on Malachar's shoulder as he falls to one "
                    "knee. He does not chase it away. \"Lira?\" he whispers.",
    },
    "skyspire": {
        "stages": [
            _stage("The Observatory Steps",
                   "The huntress, the archer and an apprentice from Greenhollow guard the "
                   "way to the observatory.",
                   "stellara.jfif", "lyra.png", "albin.jfif"),
            _stage("The Drifting Cathedral",
                   "Elysia's cathedral is anchored for one night. Its guardians do not "
                   "like visitors.",
                   "elysia.jfif", "uriel.jfif", "seraphiel.jfif"),
            _stage("Where Stars Fall",
                   "Astra draws the stars down onto the battlefield. Lyra keeps shooting "
                   "more of them loose.",
                   "astra.jfif", "lyra.png", "uriel.jfif"),
        ],
        "epilogue": "Astra looks up at the half-finished map in the sky. \"Not yet,\" she "
                    "tells the stars. They seem relieved.",
    },
    "greenhollow": {
        "stages": [
            _stage("Market Day Brawl",
                   "A misunderstanding at the market turns into a brawl. The farm boy swings "
                   "his grandfather's sword.",
                   "tobin.jfif", "albin.jfif", "wren.jfif"),
            _stage("The Mirewood",
                   "Glowing mushrooms, a runaway slime and an alchemist who does not want "
                   "to be followed.",
                   "silas.jfif", "wren.jfif", "maelis.jfif"),
            _stage("The Witch of the Swamp",
                   "Grizelda has been expecting you. She even made tea.",
                   "grizelda.jfif", "silas.jfif", "wren.jfif"),
        ],
        "epilogue": "Grizelda dusts off her apron. \"Not bad. The Box chose well.\" Then she "
                    "hums the lullaby the Wardens used to sing.",
    },
    "sylvaran": {
        "stages": [
            _stage("The Archers' Glade",
                   "Two rival archers and a young ranger test every traveler who enters "
                   "the Wilds.",
                   "faelyn.jfif", "rosalind.jfif", "rowan.jfif"),
            _stage("The Moon Garden",
                   "The moon flowers are wilting, and their keepers will not let anyone "
                   "near them.",
                   "elowen.jfif", "liesel.jfif", "verdana.jfif"),
            _stage("The Old Grove",
                   "Under the oldest tree, the master archer and the voice of the grove "
                   "guard the child the forest gave birth to.",
                   "thalion.jfif", "sylva.jfif", "verdana.jfif"),
        ],
        "epilogue": "The roots beat like a second heart under your feet. Sylva watches "
                    "Verdana and says nothing.",
    },
    "aurelian": {
        "stages": [
            _stage("Ithrel's Doors",
                   "The shelter of Ithrel defends its doors from anyone who looks like "
                   "trouble. You look like trouble.",
                   "annelise.jfif", "maelis.jfif", "albin.jfif"),
            _stage("The Temple of Solmarr",
                   "The priestess of noon and her stonemason guard the rebuilt temple.",
                   "solara.jfif", "cassius.png", "valeria.jfif"),
            _stage("The Lion's Gate",
                   "The last lion knight and the golden twins hold the capital's gate, "
                   "together for the first time since the Sundering.",
                   "leoric.jfif", "aurelius.jfif", "valeria.jfif"),
        ],
        "epilogue": "Aurelius removes his helm for the first time in years. \"We held the "
                    "gate,\" Valeria tells him. \"Both of us, this time.\"",
    },
    "hoshigane": {
        "stages": [
            _stage("The Dojo Steps",
                   "The younger brother wants to prove himself. He brought friends.",
                   "ryuji.jfif", "hayato.jfif", "jory.jfif"),
            _stage("The Burned Castle",
                   "In the ruins of the Tonbo castle, a shadow guards the last dragonfly "
                   "swordsman.",
                   "kage.jfif", "kaito.jfif", "ryuji.jfif"),
            _stage("Twin Petals",
                   "Kaito and Hayato draw as one under the cherry trees. Kage watches from "
                   "the branches.",
                   "kaito.jfif", "hayato.jfif", "kage.jfif"),
        ],
        "epilogue": "Kage sheathes his blade and finally looks Kaito in the eyes. \"It was "
                    "me, at the well.\" Kaito bows. \"Thank you.\"",
    },
    "spirehollow": {
        "stages": [
            _stage("Rooftop Chase",
                   "A pickpocket, a con artist and a relic hunter would like your purse.",
                   "jory.jfif", "vexa.jfif", "kael.jfif"),
            _stage("The Guild's Enforcer",
                   "The thieves' guild sends its enforcer, and a card sharp who owes "
                   "everyone money.",
                   "corvus.jfif", "lucan.jfif", "vexa.jfif"),
            _stage("The Masked Contract",
                   "The masked assassin, the rooftop hunter and the enforcer who never "
                   "catches her meet on the highest spire.",
                   "vesper.jfif", "nyra.jfif", "corvus.jfif"),
        ],
        "epilogue": "Corvus lowers his collar. Nyra drops her blade. \"Corin?\" The rooftops "
                    "are silent for a long time.",
    },
    "ironfang": {
        "stages": [
            _stage("The Clan Road",
                   "Clan warriors block the mountain road, as they have for three hundred "
                   "years.",
                   "brannoc.jfif", "garrick.jfif", "torvin.jfif"),
            _stage("The Rune Library",
                   "The scholar of runes is reading something he should not. His guards "
                   "would rather you did not interrupt.",
                   "eldric.png", "brannoc.jfif", "garrick.jfif"),
            _stage("The Warlord Who Cannot Die",
                   "Gorvane comes down from his throne of axes, with his son and his "
                   "scholar at his side.",
                   "gorvane.jfif", "eldric.png", "brannoc.jfif"),
        ],
        "epilogue": "Gorvane falls, and gets up, and laughs. Brannoc does not lower his axe. "
                    "\"Not the fifth time,\" his father says. \"Not yet.\"",
    },
    "thalassar": {
        "stages": [
            _stage("The Tidewatch Shore",
                   "The Tidewatch patrols the shore with a spellbreaker and a puppeteer who "
                   "hums hymns.",
                   "isolde.jfif", "maren.jfif", "odette.jfif"),
            _stage("The Drowned Temple",
                   "The winged priestess has come down to the drowned temple to take back "
                   "what she lost.",
                   "celestine.png", "odette.jfif", "maren.jfif"),
            _stage("The Tide-Witch's Song",
                   "Under the full moon, Lunara sings, and the sisters of the tide stand "
                   "with her.",
                   "lunara.jfif", "celestine.png", "isolde.jfif"),
        ],
        "epilogue": "The moon rises and Lunara turns toward the water. Isolde takes her hand. "
                    "This time, she does not let go.",
    },
    "cinderpeak": {
        "stages": [
            _stage("Lava Fields",
                   "The heir of the Everfire, his best friend and a herbalist with a fox "
                   "made of fire.",
                   "torvin.jfif", "pyralis.jfif", "liesel.jfif"),
            _stage("The Dragon's Nest",
                   "Drakara guards her mother's nest. Nobody gets near the egg.",
                   "drakara.jfif", "pyralis.jfif", "torvin.jfif"),
            _stage("The Everfire",
                   "In the heart of the volcano, the knight who swallowed the flame waits "
                   "with the two people he cannot tell the truth to.",
                   "ignis.jfif", "drakara.jfif", "pyralis.jfif"),
        ],
        "epilogue": "Ignis looks at Drakara, then at Pyralis. The flame in his chest flickers. "
                    "\"Soon,\" he tells the mountain.",
    },
    "cogsreach": {
        "stages": [
            _stage("Foundry Raid",
                   "You walk into the middle of a vault robbery. The outlaws do not like "
                   "witnesses.",
                   "scarlett.jfif", "brina.jfif", "kael.jfif"),
            _stage("The Storm Tower",
                   "The storm tower of Voltaris is failing, and its keepers think you are "
                   "here to make it worse.",
                   "ophira.jfif", "maren.jfif", "dorian.jfif"),
            _stage("Overclock",
                   "The guard, the outlaw and the gunsmith, for once on the same side.",
                   "dorian.jfif", "scarlett.jfif", "brina.jfif"),
        ],
        "epilogue": "Scarlett tips her hat. \"Tenth time, Dorian.\" He lets her go again. "
                    "Somewhere, Brina bolts the last plate onto the airship.",
    },
}

_REGION_NAMES = {region["id"]: region["name"] for region in REGIONS}


class CampaignError(ValueError):
    """Fase inexistente ou ainda fechada."""


def stage_attribute(region_id):
    return f"{STAGE_ATTRIBUTE_PREFIX}{region_id}"


def progress_from_item(item):
    """{região: fases vencidas} a partir do item de RegionProgressTable."""
    progress = {}
    for region_id in CAMPAIGN:
        value = (item or {}).get(stage_attribute(region_id), {}).get("N")
        progress[region_id] = int(value) if value else 0
    return progress


def get_stage(region_id, stage):
    """Definição da fase (1 = primeira) ou None."""
    region = CAMPAIGN.get(region_id)
    if not region or not isinstance(stage, int) or not 1 <= stage <= len(region["stages"]):
        return None
    return region["stages"][stage - 1]


def enemy_level(player_level, stage):
    offset = STAGE_RULES[stage - 1]["levelOffset"]
    return max(1, min(MAX_LEVEL, player_level + offset))


def check_stage(region_id, stage, cleared):
    """Confere se a fase existe e está aberta para quem venceu `cleared` fases."""
    if get_stage(region_id, stage) is None:
        raise CampaignError("Unknown campaign stage.")
    if stage > cleared + 1:
        raise CampaignError("Clear the previous stage first.")


def stage_setup(region_id, stage, player_level):
    """O que a batalha precisa para montar a fase (inimigos, nível, força...)."""
    spec = get_stage(region_id, stage)
    rules = STAGE_RULES[stage - 1]
    return {
        "region": region_id,
        "stage": stage,
        "boss": stage == STAGES_PER_REGION,
        "label": f"{_REGION_NAMES[region_id]} · {spec['name']}",
        "enemies": [get_character(name) for name in spec["enemies"]],
        "enemyLevel": enemy_level(player_level, stage),
        "power": rules["power"],
        "experience": rules["experience"],
    }


def first_clear_reward(stage):
    return STAGE_RULES[stage - 1]["reward"]


def epilogue(region_id):
    return CAMPAIGN[region_id]["epilogue"]


def public_campaign(progress, player_level):
    """Regiões, fases (com quem luta e o que paga) e o progresso do jogador."""
    regions = []
    for region_id, region in CAMPAIGN.items():
        cleared = progress.get(region_id, 0)
        complete = cleared >= len(region["stages"])
        stages = []
        for index, spec in enumerate(region["stages"], start=1):
            rules = STAGE_RULES[index - 1]
            stages.append(
                {
                    "stage": index,
                    "name": spec["name"],
                    "intro": spec["intro"],
                    "boss": index == STAGES_PER_REGION,
                    "enemies": [
                        {
                            "file_name": name,
                            "name": get_character(name)["name"],
                            "rarity": get_character(name)["rarity"],
                        }
                        for name in spec["enemies"]
                    ],
                    "enemyLevel": enemy_level(player_level, index),
                    "experience": rules["experience"],
                    "reward": rules["reward"],
                    "cleared": index <= cleared,
                    "unlocked": index <= cleared + 1,
                }
            )
        regions.append(
            {
                "region": region_id,
                "regionName": _REGION_NAMES[region_id],
                "cleared": cleared,
                "total": len(region["stages"]),
                "complete": complete,
                # O epílogo só sai do servidor depois de vencer o chefe.
                "epilogue": region["epilogue"] if complete else None,
                "stages": stages,
            }
        )
    return regions
