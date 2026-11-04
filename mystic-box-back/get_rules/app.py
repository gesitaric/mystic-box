"""GET /rules: regras do jogo para a tela de ajuda (Grimório).

Público: as regras não dependem do jogador. Os valores saem das mesmas
constantes que as outras Lambdas usam (`mystic_shared`), então a ajuda nunca
fica desatualizada em relação ao que o servidor aplica.
"""

import json
import os

from mystic_shared.rules import public_rules
from mystic_shared.summon_token import TOKEN_TTL_SECONDS

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

SUMMON_COOLDOWN_SECONDS = int(os.environ.get("SUMMON_COOLDOWN_SECONDS", "3600"))


def response(status_code, body, headers=None):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, **(headers or {})},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    rules = public_rules(SUMMON_COOLDOWN_SECONDS, TOKEN_TTL_SECONDS)
    return response(200, rules, {"Cache-Control": "public, max-age=300"})
