"""Definições das cartas e regras do sorteio e da loja.

Fonte única da verdade: nome, raridade, imagem e preço (de compra e de venda na loja) de cada carta
vivem SÓ aqui. Nenhuma Lambda deve confiar nesses dados vindos do frontend;
quando precisar deles, procure a carta pelo `file_name` com `get_character`.
"""

import random

CHARACTERS = [
    {"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif", "price": 250},
    {"name": "Boreas", "rarity": 5, "file_name": "boreas.jfif", "price": 250},
    {"name": "Astra", "rarity": 5, "file_name": "astra.jfif", "price": 250},
    {"name": "Seraphiel", "rarity": 5, "file_name": "seraphiel.jfif", "price": 250},
    {"name": "Ignis", "rarity": 5, "file_name": "ignis.jfif", "price": 250},
    {"name": "Leoric", "rarity": 5, "file_name": "leoric.jfif", "price": 250},
    {"name": "Lunara", "rarity": 5, "file_name": "lunara.jfif", "price": 250},
    {"name": "Mortis", "rarity": 5, "file_name": "mortis.jfif", "price": 250},
    {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif", "price": 50},
    {"name": "Solara", "rarity": 4, "file_name": "solara.jfif", "price": 50},
    {"name": "Aurelius", "rarity": 4, "file_name": "aurelius.jfif", "price": 50},
    {"name": "Scarlett", "rarity": 4, "file_name": "scarlett.jfif", "price": 50},
    {"name": "Sylva", "rarity": 4, "file_name": "sylva.jfif", "price": 50},
    {"name": "Rosalind", "rarity": 4, "file_name": "rosalind.jfif", "price": 50},
    {"name": "Thalion", "rarity": 4, "file_name": "thalion.jfif", "price": 50},
    {"name": "Vesper", "rarity": 4, "file_name": "vesper.jfif", "price": 50},
    {"name": "Pyralis", "rarity": 4, "file_name": "pyralis.jfif", "price": 50},
    {"name": "Glacius", "rarity": 4, "file_name": "glacius.jfif", "price": 50},
    {"name": "Isolde", "rarity": 4, "file_name": "isolde.jfif", "price": 50},
    {"name": "Elowen", "rarity": 4, "file_name": "elowen.jfif", "price": 50},
    {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif", "price": 10},
    {"name": "Corvus", "rarity": 3, "file_name": "corvus.jfif", "price": 10},
]

_BY_FILE_NAME = {character["file_name"]: character for character in CHARACTERS}

SUMMON_SIZE = 3

# Máximo de cópias vendidas de uma vez. Uma transação do DynamoDB aceita até
# 100 itens: um para a carteira e o resto para as cartas removidas.
MAX_SELL_QUANTITY = 99

RARITY_WEIGHTS = {5: 1, 4: 6, 3: 40}

# A última carta da invocação tem chances um pouco maiores de ser rara.
LAST_CARD_RARITY_WEIGHTS = {5: 2, 4: 8, 3: 40}


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
