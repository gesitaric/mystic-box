import json
import random

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

CHARACTERS = [
    {"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif"},
    {"name": "Boreas", "rarity": 5, "file_name": "boreas.jfif"},
    {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"},
    {"name": "Seraphiel", "rarity": 5, "file_name": "seraphiel.jfif"},
    {"name": "Ignis", "rarity": 5, "file_name": "ignis.jfif"},
    {"name": "Leoric", "rarity": 5, "file_name": "leoric.jfif"},
    {"name": "Lunara", "rarity": 5, "file_name": "lunara.jfif"},
    {"name": "Mortis", "rarity": 5, "file_name": "mortis.jfif"},
    {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif"},
    {"name": "Solara", "rarity": 4, "file_name": "solara.jfif"},
    {"name": "Aurelius", "rarity": 4, "file_name": "aurelius.jfif"},
    {"name": "Scarlett", "rarity": 4, "file_name": "scarlett.jfif"},
    {"name": "Sylva", "rarity": 4, "file_name": "sylva.jfif"},
    {"name": "Rosalind", "rarity": 4, "file_name": "rosalind.jfif"},
    {"name": "Thalion", "rarity": 4, "file_name": "thalion.jfif"},
    {"name": "Vesper", "rarity": 4, "file_name": "vesper.jfif"},
    {"name": "Pyralis", "rarity": 4, "file_name": "pyralis.jfif"},
    {"name": "Glacius", "rarity": 4, "file_name": "glacius.jfif"},
    {"name": "Isolde", "rarity": 4, "file_name": "isolde.jfif"},
    {"name": "Elowen", "rarity": 4, "file_name": "elowen.jfif"},
    {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif"},
    {"name": "Corvus", "rarity": 3, "file_name": "corvus.jfif"},
]

SUMMON_SIZE = 3

RARITY_WEIGHTS = {5: 1, 4: 6, 3: 40}

# A última carta da invocação tem chances um pouco maiores de ser rara.
LAST_CARD_RARITY_WEIGHTS = {5: 2, 4: 8, 3: 40}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
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


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    return response(200, {"cards": draw_cards()})
