"""GET /world: o mapa-múndi (regiões, a história do mundo e quem vem de onde).

Público. As histórias completas de cada carta só aparecem na coleção
(`GET /users/me/cards`); aqui vão só nome, raridade e título.
"""

import json

from mystic_shared.lore import public_world
from mystic_shared.omens import public_omen

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}


def response(status_code, body, headers=None):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, **(headers or {})},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    # O boato da semana muda toda segunda; o cache curto acompanha a troca.
    world = {**public_world(), "omen": public_omen()}
    return response(200, world, {"Cache-Control": "public, max-age=300"})
