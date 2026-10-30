import json
import random

CHARACTERS = [
    {"name": "Malachar", "rarity": 5, "file_name": "malachar.jfif"},
    {"name": "Boreas", "rarity": 5, "file_name": "boreas.jfif"},
    {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"},
    {"name": "Seraphiel", "rarity": 5, "file_name": "seraphiel.jfif"},
    {"name": "Ignis", "rarity": 5, "file_name": "ignis.jfif"},
    {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif"},
    {"name": "Solara", "rarity": 4, "file_name": "solara.jfif"},
    {"name": "Aurelius", "rarity": 4, "file_name": "aurelius.jfif"},
    {"name": "Scarlett", "rarity": 4, "file_name": "scarlett.jfif"},
    {"name": "Sylva", "rarity": 4, "file_name": "sylva.jfif"},
    {"name": "Rosalind", "rarity": 4, "file_name": "rosalind.jfif"},
    {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif"},
]

RARITY_WEIGHTS = {5: 1, 4: 6, 3: 40}


def draw_card():
    weights = [RARITY_WEIGHTS[character["rarity"]] for character in CHARACTERS]
    return random.choices(CHARACTERS, weights=weights, k=1)[0]


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"cards": [draw_card()]}),
    }
