"""Boato da semana: a cada semana uma região fica em destaque no mundo.

- A região da semana segue um rodízio fixo pelas regiões com personagens,
  trocando toda segunda-feira à 00:00 UTC (OMEN_EPOCH é uma segunda-feira).
- No sorteio, os personagens da região têm FEATURED_SUMMON_MULTIPLIER vezes
  mais chance dentro da raridade deles (a chance de cada raridade não muda).
- Em batalhas contra o computador e na campanha, um time com pelo menos uma
  carta da região ganha OMEN_EXPERIENCE_BONUS a mais de experiência.

Tudo é calculado no servidor a partir da data.
"""

from datetime import date, datetime, time, timedelta, timezone

from .lore import REGIONS
from .mastery import regions_with_residents, residents

OMEN_EPOCH = date(2026, 1, 5)
FEATURED_SUMMON_MULTIPLIER = 3
OMEN_EXPERIENCE_BONUS = 0.25

# O que se ouve no mundo quando cada região está em destaque.
OMENS = {
    "hrimvald": ("The Long Howl",
                 "The wind-wolves howl for seven nights. Champions of the north answer the "
                 "Box more readily while the howl lasts."),
    "zephyrine": ("The Isles Draw Near",
                  "The floating isles drift close enough to see from the ground. The sky "
                  "guard is recruiting."),
    "nocthaven": ("The Night of Lanterns",
                  "Nocthaven lights a lantern for every soul in Malachar's tome. The dead are "
                  "restless, and so are their champions."),
    "skyspire": ("The Star Shower",
                 "Stars are falling over Skyspire faster than Stellara can catch them. "
                 "Lyra swears it is not her fault."),
    "greenhollow": ("Harvest Festival",
                    "Greenhollow throws its harvest festival. Grizelda brought a cake. "
                    "Nobody has dared to eat it."),
    "sylvaran": ("The Moonbloom",
                 "The moon flowers bloom all at once for the first time since the "
                 "Sundering. The old grove is singing."),
    "aurelian": ("The Lion's Tourney",
                 "The capital holds a tourney in memory of the Lion Order. A golden knight "
                 "has entered under a false name."),
    "hoshigane": ("Cherry Blossom Duels",
                  "Under the falling petals, every duel in Hoshigane is sacred. Kaito and "
                  "Hayato have booked the main garden."),
    "spirehollow": ("The Guild's Amnesty",
                    "The thieves' guild declares a week of amnesty. Nobody believes it. "
                    "Everybody takes advantage of it."),
    "ironfang": ("The Gathering of Clans",
                 "The clans gather to count Gorvane's deaths. The war drums can be heard "
                 "from three realms away."),
    "thalassar": ("The Spring Tide",
                  "The spring tide uncovers the steps of a drowned temple. Colette has "
                  "started singing louder."),
    "cinderpeak": ("The Mountain Stirs",
                   "Cinderpeak rumbles and the lava glows brighter. The stones are singing "
                   "their warning again."),
    "cogsreach": ("The Grand Exposition",
                  "Cogsreach shows off its newest inventions. Someone has already robbed "
                  "the baron's pavilion."),
}

_REGION_NAMES = {region["id"]: region["name"] for region in REGIONS}


def _week_index(now):
    return (now.date() - OMEN_EPOCH).days // 7


def current_region(now=None):
    """Região em destaque na semana de `now` (UTC)."""
    now = now or datetime.now(timezone.utc)
    regions = regions_with_residents()
    return regions[_week_index(now) % len(regions)]


def featured_file_names(now=None):
    """Personagens da região da semana (mais chance no sorteio)."""
    return set(residents(current_region(now)))


def public_omen(now=None):
    """O boato da semana, o que ele muda e quando acaba."""
    now = now or datetime.now(timezone.utc)
    region_id = current_region(now)
    title, text = OMENS[region_id]
    ends = OMEN_EPOCH + timedelta(weeks=_week_index(now) + 1)
    return {
        "region": region_id,
        "regionName": _REGION_NAMES[region_id],
        "title": title,
        "text": text,
        "summonMultiplier": FEATURED_SUMMON_MULTIPLIER,
        "experienceBonusPercent": round(OMEN_EXPERIENCE_BONUS * 100),
        "endsAt": datetime.combine(ends, time(), timezone.utc).isoformat(),
    }
