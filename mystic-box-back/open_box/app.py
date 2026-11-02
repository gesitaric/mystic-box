import json

from botocore.exceptions import ClientError
from mystic_shared import summon_token
from mystic_shared.cards import draw_cards, public_card

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    drawn = draw_cards()

    try:
        # Só este token (e não as cartas) é aceito depois por POST /users/me/cards.
        token = summon_token.issue(character["file_name"] for character in drawn)
    except ClientError:
        return response(500, {"message": "Não foi possível abrir a caixa."})

    return response(
        200,
        {
            "cards": [public_card(character) for character in drawn],
            "summonToken": token,
        },
    )
