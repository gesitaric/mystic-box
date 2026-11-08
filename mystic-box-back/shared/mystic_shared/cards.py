"""Definições das cartas e regras do sorteio e do mercado (loja).

Fonte única da verdade: nome, raridade, imagem, elemento e arquétipo de
batalha de cada carta vivem SÓ aqui (os atributos de batalha derivados deles
ficam em `stats.py`), assim como os limites de preço e de quantidade dos
anúncios do mercado. Nenhuma Lambda deve confiar nesses dados vindos do
frontend; quando precisar deles, procure a carta pelo `file_name` com
`get_character`.

O mercado tem estoque: cartas novas só nascem do sorteio. A loja só vende o
que outros jogadores anunciaram, pelo preço que eles escolheram.
"""

import random

CHARACTERS = [
    {"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif", "element": "umbra", "archetype": "arcanist"},
    {"name": "Boreas", "rarity": 5, "file_name": "boreas.jfif", "element": "gale", "archetype": "vanguard"},
    {"name": "Astra", "rarity": 5, "file_name": "astra.jfif", "element": "lumen", "archetype": "arcanist"},
    {"name": "Seraphiel", "rarity": 5, "file_name": "seraphiel.jfif", "element": "lumen", "archetype": "mystic"},
    {"name": "Ignis", "rarity": 5, "file_name": "ignis.jfif", "element": "ember", "archetype": "duelist"},
    {"name": "Leoric", "rarity": 5, "file_name": "leoric.jfif", "element": "terra", "archetype": "vanguard"},
    {"name": "Lunara", "rarity": 5, "file_name": "lunara.jfif", "element": "tide", "archetype": "mystic"},
    {"name": "Mortis", "rarity": 5, "file_name": "mortis.jfif", "element": "umbra", "archetype": "trickster"},
    {"name": "Drakara", "rarity": 5, "file_name": "drakara.jfif", "element": "ember", "archetype": "duelist"},
    {"name": "Gorvane", "rarity": 5, "file_name": "gorvane.jfif", "element": "terra", "archetype": "duelist"},
    {"name": "Elysia", "rarity": 5, "file_name": "elysia.jfif", "element": "gale", "archetype": "mystic"},
    {"name": "Uriel", "rarity": 5, "file_name": "uriel.jfif", "element": "lumen", "archetype": "vanguard"},
    {"name": "Celestine", "rarity": 5, "file_name": "celestine.png", "element": "tide", "archetype": "arcanist"},
    {"name": "Lyra", "rarity": 5, "file_name": "lyra.png", "element": "gale", "archetype": "trickster"},
    {"name": "Zarathor", "rarity": 5, "file_name": "zarathor.jfif", "element": "umbra", "archetype": "summoner"},
    {"name": "Vaelora", "rarity": 5, "file_name": "vaelora.jfif", "element": "gale", "archetype": "summoner"},
    {"name": "Draemir", "rarity": 5, "file_name": "draemir.jfif", "element": "lumen", "archetype": "duelist"},
    {"name": "Kyrielle", "rarity": 5, "file_name": "kyrielle.jfif", "element": "volt", "archetype": "summoner"},
    {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif", "element": "gale", "archetype": "duelist"},
    {"name": "Solara", "rarity": 4, "file_name": "solara.jfif", "element": "ember", "archetype": "arcanist"},
    {"name": "Aurelius", "rarity": 4, "file_name": "aurelius.jfif", "element": "lumen", "archetype": "vanguard"},
    {"name": "Scarlett", "rarity": 4, "file_name": "scarlett.jfif", "element": "ember", "archetype": "duelist"},
    {"name": "Sylva", "rarity": 4, "file_name": "sylva.jfif", "element": "terra", "archetype": "mystic"},
    {"name": "Rosalind", "rarity": 4, "file_name": "rosalind.jfif", "element": "terra", "archetype": "trickster"},
    {"name": "Thalion", "rarity": 4, "file_name": "thalion.jfif", "element": "gale", "archetype": "duelist"},
    {"name": "Vesper", "rarity": 4, "file_name": "vesper.jfif", "element": "umbra", "archetype": "arcanist"},
    {"name": "Pyralis", "rarity": 4, "file_name": "pyralis.jfif", "element": "ember", "archetype": "arcanist"},
    {"name": "Glacius", "rarity": 4, "file_name": "glacius.jfif", "element": "tide", "archetype": "vanguard"},
    {"name": "Isolde", "rarity": 4, "file_name": "isolde.jfif", "element": "tide", "archetype": "mystic"},
    {"name": "Elowen", "rarity": 4, "file_name": "elowen.jfif", "element": "terra", "archetype": "mystic"},
    {"name": "Hayato", "rarity": 4, "file_name": "hayato.jfif", "element": "gale", "archetype": "duelist"},
    {"name": "Maren", "rarity": 4, "file_name": "maren.jfif", "element": "tide", "archetype": "trickster"},
    {"name": "Fenric", "rarity": 4, "file_name": "fenric.jfif", "element": "umbra", "archetype": "duelist"},
    {"name": "Faelyn", "rarity": 4, "file_name": "faelyn.jfif", "element": "gale", "archetype": "trickster"},
    {"name": "Amethia", "rarity": 4, "file_name": "amethia.jfif", "element": "umbra", "archetype": "arcanist"},
    {"name": "Valeria", "rarity": 4, "file_name": "valeria.jfif", "element": "lumen", "archetype": "duelist"},
    {"name": "Stellara", "rarity": 4, "file_name": "stellara.jfif", "element": "lumen", "archetype": "mystic"},
    {"name": "Morwen", "rarity": 4, "file_name": "morwen.jfif", "element": "umbra", "archetype": "trickster"},
    {"name": "Kage", "rarity": 4, "file_name": "kage.jfif", "element": "umbra", "archetype": "duelist"},
    {"name": "Odette", "rarity": 4, "file_name": "odette.jfif", "element": "tide", "archetype": "mystic"},
    {"name": "Nocturna", "rarity": 4, "file_name": "nocturna.jfif", "element": "umbra", "archetype": "arcanist"},
    {"name": "Eldric", "rarity": 4, "file_name": "eldric.png", "element": "terra", "archetype": "arcanist"},
    {"name": "Ravenna", "rarity": 4, "file_name": "ravenna.png", "element": "umbra", "archetype": "trickster"},
    {"name": "Cassius", "rarity": 4, "file_name": "cassius.png", "element": "terra", "archetype": "vanguard"},
    {"name": "Nyra", "rarity": 4, "file_name": "nyra.jfif", "element": "umbra", "archetype": "duelist"},
    {"name": "Dorian", "rarity": 4, "file_name": "dorian.jfif", "element": "volt", "archetype": "vanguard"},
    {"name": "Grizelda", "rarity": 4, "file_name": "grizelda.jfif", "element": "terra", "archetype": "summoner"},
    {"name": "Ophira", "rarity": 4, "file_name": "ophira.jfif", "element": "volt", "archetype": "arcanist"},
    {"name": "Verdana", "rarity": 4, "file_name": "verdana.jfif", "element": "terra", "archetype": "mystic"},
    {"name": "Tavik", "rarity": 4, "file_name": "tavik.jfif", "element": "volt", "archetype": "summoner"},
    {"name": "Lucan", "rarity": 4, "file_name": "lucan.jfif", "element": "umbra", "archetype": "trickster"},
    {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif", "element": "terra", "archetype": "vanguard"},
    {"name": "Corvus", "rarity": 3, "file_name": "corvus.jfif", "element": "umbra", "archetype": "trickster"},
    {"name": "Tobin", "rarity": 3, "file_name": "tobin.jfif", "element": "terra", "archetype": "duelist"},
    {"name": "Garrick", "rarity": 3, "file_name": "garrick.jfif", "element": "ember", "archetype": "vanguard"},
    {"name": "Maelis", "rarity": 3, "file_name": "maelis.jfif", "element": "tide", "archetype": "mystic"},
    {"name": "Jory", "rarity": 3, "file_name": "jory.jfif", "element": "gale", "archetype": "duelist"},
    {"name": "Albin", "rarity": 3, "file_name": "albin.jfif", "element": "lumen", "archetype": "mystic"},
    {"name": "Brina", "rarity": 3, "file_name": "brina.jfif", "element": "tide", "archetype": "arcanist"},
    {"name": "Silas", "rarity": 3, "file_name": "silas.jfif", "element": "umbra", "archetype": "arcanist"},
    {"name": "Kael", "rarity": 3, "file_name": "kael.jfif", "element": "ember", "archetype": "duelist"},
    {"name": "Vexa", "rarity": 3, "file_name": "vexa.jfif", "element": "gale", "archetype": "trickster"},
    {"name": "Torvin", "rarity": 3, "file_name": "torvin.jfif", "element": "terra", "archetype": "vanguard"},
    {"name": "Annelise", "rarity": 3, "file_name": "annelise.jfif", "element": "lumen", "archetype": "mystic"},
    {"name": "Brannoc", "rarity": 3, "file_name": "brannoc.jfif", "element": "terra", "archetype": "vanguard"},
    {"name": "Ryuji", "rarity": 3, "file_name": "ryuji.jfif", "element": "gale", "archetype": "duelist"},
    {"name": "Liesel", "rarity": 3, "file_name": "liesel.jfif", "element": "ember", "archetype": "summoner"},
    {"name": "Wren", "rarity": 3, "file_name": "wren.jfif", "element": "tide", "archetype": "summoner"},
]

_BY_FILE_NAME = {character["file_name"]: character for character in CHARACTERS}

SUMMON_SIZE = 3

# Mercado entre jogadores. Um anúncio é uma cópia de uma carta, com o preço
# escolhido pelo vendedor dentro da faixa da raridade (evita anúncios de 1
# fragmento só para passar moeda de uma conta para outra).
LISTING_PRICE_LIMITS = {
    3: {"min": 5, "max": 500},
    4: {"min": 25, "max": 2500},
    5: {"min": 125, "max": 12500},
}

# Cópias anunciadas de uma vez. A transação tem 2 itens por cópia (sai da
# coleção, entra no mercado) mais 1 da carteira, e o DynamoDB aceita até 100.
MAX_LISTING_QUANTITY = 10

# Anúncios ativos por jogador ao mesmo tempo.
MAX_ACTIVE_LISTINGS = 30

# Pesos por carta: ao mudar a quantidade de cartas de cada raridade, revise-os
# para manter a chance total de cada raridade (hoje ~4,5% 5★, ~44% 4★, ~51% 3★,
# com 18 cartas 5★, 33 4★ e 17 3★).
RARITY_WEIGHTS = {5: 7, 4: 38, 3: 85}

# A última carta da invocação tem chances um pouco maiores de ser rara
# (~8,5% 5★, ~50% 4★, ~42% 3★).
LAST_CARD_RARITY_WEIGHTS = {5: 16, 4: 51, 3: 83}


def get_character(file_name):
    """Definição da carta com esse `file_name`, ou None se não existir."""
    return _BY_FILE_NAME.get(file_name)


def listing_price_range(character):
    """Faixa de preço (por cópia) permitida ao anunciar a carta, ou None."""
    if character is None:
        return None
    return dict(LISTING_PRICE_LIMITS[character["rarity"]])


def is_valid_listing_price(character, price):
    """Se `price` é um preço aceito para anunciar uma cópia da carta."""
    price_range = listing_price_range(character)
    if price_range is None or not isinstance(price, int) or isinstance(price, bool):
        return False
    return price_range["min"] <= price <= price_range["max"]


def max_listing_quantity(character, owned_quantity):
    """Quantas cópias o jogador pode anunciar de uma vez (0 = não pode)."""
    if character is None:
        return 0
    return min(owned_quantity, MAX_LISTING_QUANTITY)


def public_card(character):
    """Campos da carta que podem ser mostrados ao jogador durante a invocação."""
    return {
        "name": character["name"],
        "rarity": character["rarity"],
        "file_name": character["file_name"],
    }


def card_weights(available, rarity_weights, featured=None, multiplier=1):
    """Peso de cada carta em `available`.

    Cartas em `featured` (boato da semana) pesam `multiplier` vezes mais que as
    outras da mesma raridade, sem mudar a chance total de cada raridade.
    """
    featured = featured or set()
    counts, boosted = {}, {}
    for character in available:
        rarity = character["rarity"]
        counts[rarity] = counts.get(rarity, 0) + 1
        if character["file_name"] in featured:
            boosted[rarity] = boosted.get(rarity, 0) + 1
    weights = []
    for character in available:
        rarity = character["rarity"]
        base = rarity_weights[rarity]
        if not boosted.get(rarity) or multiplier == 1:
            weights.append(base)
            continue
        # Mesma soma da raridade: n * base = (n - f) * w + f * w * multiplier.
        n, f = counts[rarity], boosted[rarity]
        unit = base * n / (n - f + f * multiplier)
        weights.append(unit * multiplier if character["file_name"] in featured else unit)
    return weights


def draw_cards(count=SUMMON_SIZE, featured=None, multiplier=1):
    """Sorteia `count` personagens distintos; o último usa pesos mais generosos.

    `featured`/`multiplier`: personagens com mais chance (boato da semana).
    """
    available = list(CHARACTERS)
    drawn = []

    for position in range(count):
        rarity_weights = (
            LAST_CARD_RARITY_WEIGHTS if position == count - 1 else RARITY_WEIGHTS
        )
        weights = card_weights(available, rarity_weights, featured, multiplier)
        character = random.choices(available, weights=weights, k=1)[0]
        available.remove(character)
        drawn.append(character)

    return drawn
