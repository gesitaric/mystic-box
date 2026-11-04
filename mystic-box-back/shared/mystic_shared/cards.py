"""Definições das cartas e regras do sorteio e da loja.

Fonte única da verdade: nome, raridade, imagem, preço (de compra e de venda na loja),
elemento e arquétipo de batalha de cada carta vivem SÓ aqui (os atributos de
batalha derivados deles ficam em `stats.py`). Nenhuma Lambda deve confiar nesses dados vindos do frontend;
quando precisar deles, procure a carta pelo `file_name` com `get_character`.
"""

import random

CHARACTERS = [
    {"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif", "price": 250, "element": "umbra", "archetype": "arcanist"},
    {"name": "Boreas", "rarity": 5, "file_name": "boreas.jfif", "price": 250, "element": "gale", "archetype": "vanguard"},
    {"name": "Astra", "rarity": 5, "file_name": "astra.jfif", "price": 250, "element": "lumen", "archetype": "arcanist"},
    {"name": "Seraphiel", "rarity": 5, "file_name": "seraphiel.jfif", "price": 250, "element": "lumen", "archetype": "mystic"},
    {"name": "Ignis", "rarity": 5, "file_name": "ignis.jfif", "price": 250, "element": "ember", "archetype": "duelist"},
    {"name": "Leoric", "rarity": 5, "file_name": "leoric.jfif", "price": 250, "element": "terra", "archetype": "vanguard"},
    {"name": "Lunara", "rarity": 5, "file_name": "lunara.jfif", "price": 250, "element": "tide", "archetype": "mystic"},
    {"name": "Mortis", "rarity": 5, "file_name": "mortis.jfif", "price": 250, "element": "umbra", "archetype": "trickster"},
    {"name": "Drakara", "rarity": 5, "file_name": "drakara.jfif", "price": 250, "element": "ember", "archetype": "duelist"},
    {"name": "Gorvane", "rarity": 5, "file_name": "gorvane.jfif", "price": 250, "element": "terra", "archetype": "duelist"},
    {"name": "Elysia", "rarity": 5, "file_name": "elysia.jfif", "price": 250, "element": "gale", "archetype": "mystic"},
    {"name": "Uriel", "rarity": 5, "file_name": "uriel.jfif", "price": 250, "element": "lumen", "archetype": "vanguard"},
    {"name": "Celestine", "rarity": 5, "file_name": "celestine.png", "price": 250, "element": "tide", "archetype": "arcanist"},
    {"name": "Lyra", "rarity": 5, "file_name": "lyra.png", "price": 250, "element": "gale", "archetype": "trickster"},
    {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif", "price": 50, "element": "gale", "archetype": "duelist"},
    {"name": "Solara", "rarity": 4, "file_name": "solara.jfif", "price": 50, "element": "ember", "archetype": "arcanist"},
    {"name": "Aurelius", "rarity": 4, "file_name": "aurelius.jfif", "price": 50, "element": "lumen", "archetype": "vanguard"},
    {"name": "Scarlett", "rarity": 4, "file_name": "scarlett.jfif", "price": 50, "element": "ember", "archetype": "duelist"},
    {"name": "Sylva", "rarity": 4, "file_name": "sylva.jfif", "price": 50, "element": "terra", "archetype": "mystic"},
    {"name": "Rosalind", "rarity": 4, "file_name": "rosalind.jfif", "price": 50, "element": "terra", "archetype": "trickster"},
    {"name": "Thalion", "rarity": 4, "file_name": "thalion.jfif", "price": 50, "element": "gale", "archetype": "duelist"},
    {"name": "Vesper", "rarity": 4, "file_name": "vesper.jfif", "price": 50, "element": "umbra", "archetype": "arcanist"},
    {"name": "Pyralis", "rarity": 4, "file_name": "pyralis.jfif", "price": 50, "element": "ember", "archetype": "arcanist"},
    {"name": "Glacius", "rarity": 4, "file_name": "glacius.jfif", "price": 50, "element": "tide", "archetype": "vanguard"},
    {"name": "Isolde", "rarity": 4, "file_name": "isolde.jfif", "price": 50, "element": "tide", "archetype": "mystic"},
    {"name": "Elowen", "rarity": 4, "file_name": "elowen.jfif", "price": 50, "element": "terra", "archetype": "mystic"},
    {"name": "Hayato", "rarity": 4, "file_name": "hayato.jfif", "price": 50, "element": "gale", "archetype": "duelist"},
    {"name": "Maren", "rarity": 4, "file_name": "maren.jfif", "price": 50, "element": "tide", "archetype": "trickster"},
    {"name": "Fenric", "rarity": 4, "file_name": "fenric.jfif", "price": 50, "element": "umbra", "archetype": "duelist"},
    {"name": "Faelyn", "rarity": 4, "file_name": "faelyn.jfif", "price": 50, "element": "gale", "archetype": "trickster"},
    {"name": "Amethia", "rarity": 4, "file_name": "amethia.jfif", "price": 50, "element": "umbra", "archetype": "arcanist"},
    {"name": "Valeria", "rarity": 4, "file_name": "valeria.jfif", "price": 50, "element": "lumen", "archetype": "duelist"},
    {"name": "Stellara", "rarity": 4, "file_name": "stellara.jfif", "price": 50, "element": "lumen", "archetype": "mystic"},
    {"name": "Morwen", "rarity": 4, "file_name": "morwen.jfif", "price": 50, "element": "umbra", "archetype": "trickster"},
    {"name": "Kage", "rarity": 4, "file_name": "kage.jfif", "price": 50, "element": "umbra", "archetype": "duelist"},
    {"name": "Odette", "rarity": 4, "file_name": "odette.jfif", "price": 50, "element": "tide", "archetype": "mystic"},
    {"name": "Nocturna", "rarity": 4, "file_name": "nocturna.jfif", "price": 50, "element": "umbra", "archetype": "arcanist"},
    {"name": "Eldric", "rarity": 4, "file_name": "eldric.png", "price": 50, "element": "terra", "archetype": "arcanist"},
    {"name": "Ravenna", "rarity": 4, "file_name": "ravenna.png", "price": 50, "element": "umbra", "archetype": "trickster"},
    {"name": "Cassius", "rarity": 4, "file_name": "cassius.png", "price": 50, "element": "terra", "archetype": "vanguard"},
    {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif", "price": 10, "element": "terra", "archetype": "vanguard"},
    {"name": "Corvus", "rarity": 3, "file_name": "corvus.jfif", "price": 10, "element": "umbra", "archetype": "trickster"},
    {"name": "Tobin", "rarity": 3, "file_name": "tobin.jfif", "price": 10, "element": "terra", "archetype": "duelist"},
    {"name": "Garrick", "rarity": 3, "file_name": "garrick.jfif", "price": 10, "element": "ember", "archetype": "vanguard"},
    {"name": "Maelis", "rarity": 3, "file_name": "maelis.jfif", "price": 10, "element": "tide", "archetype": "mystic"},
    {"name": "Jory", "rarity": 3, "file_name": "jory.jfif", "price": 10, "element": "gale", "archetype": "duelist"},
    {"name": "Albin", "rarity": 3, "file_name": "albin.jfif", "price": 10, "element": "lumen", "archetype": "mystic"},
    {"name": "Brina", "rarity": 3, "file_name": "brina.jfif", "price": 10, "element": "tide", "archetype": "arcanist"},
    {"name": "Silas", "rarity": 3, "file_name": "silas.jfif", "price": 10, "element": "umbra", "archetype": "arcanist"},
    {"name": "Kael", "rarity": 3, "file_name": "kael.jfif", "price": 10, "element": "ember", "archetype": "duelist"},
    {"name": "Vexa", "rarity": 3, "file_name": "vexa.jfif", "price": 10, "element": "gale", "archetype": "trickster"},
    {"name": "Torvin", "rarity": 3, "file_name": "torvin.jfif", "price": 10, "element": "terra", "archetype": "vanguard"},
]

_BY_FILE_NAME = {character["file_name"]: character for character in CHARACTERS}

SUMMON_SIZE = 3

# Máximo de cópias vendidas de uma vez. Uma transação do DynamoDB aceita até
# 100 itens: um para a carteira e o resto para as cartas removidas.
MAX_SELL_QUANTITY = 99

# Pesos por carta: ao mudar a quantidade de cartas de cada raridade, revise-os
# para manter a chance total de cada raridade (hoje ~4,5% 5★, ~44% 4★, ~51% 3★).
RARITY_WEIGHTS = {5: 3, 4: 16, 3: 40}

# A última carta da invocação tem chances um pouco maiores de ser rara
# (~8,5% 5★, ~50% 4★, ~42% 3★).
LAST_CARD_RARITY_WEIGHTS = {5: 7, 4: 22, 3: 40}


def get_character(file_name):
    """Definição da carta com esse `file_name`, ou None se não existir."""
    return _BY_FILE_NAME.get(file_name)


def sell_price(character):
    """Quanto o jogador recebe ao vender a carta na loja."""
    return character["price"]


def sell_total(character, quantity):
    """Quanto o jogador recebe ao vender `quantity` cópias da carta de uma vez."""
    return sell_price(character) * quantity


def max_sell_quantity(character, owned_quantity):
    """Quantas cópias o jogador pode vender de uma vez (0 = não pode vender)."""
    if character is None:
        return 0
    return min(owned_quantity, MAX_SELL_QUANTITY)


def buy_price(character):
    """Quanto o jogador paga para comprar a carta na loja."""
    return character["price"]


def shop_catalog():
    """Cartas à venda na loja: todas as cartas do jogo."""
    return list(CHARACTERS)


def public_card(character):
    """Campos da carta que podem ser mostrados ao jogador durante a invocação."""
    return {
        "name": character["name"],
        "rarity": character["rarity"],
        "file_name": character["file_name"],
    }


def draw_cards(count=SUMMON_SIZE):
    """Sorteia `count` personagens distintos; o último usa pesos mais generosos."""
    available = list(CHARACTERS)
    drawn = []

    for position in range(count):
        rarity_weights = (
            LAST_CARD_RARITY_WEIGHTS if position == count - 1 else RARITY_WEIGHTS
        )
        weights = [rarity_weights[character["rarity"]] for character in available]
        character = random.choices(available, weights=weights, k=1)[0]
        available.remove(character)
        drawn.append(character)

    return drawn
