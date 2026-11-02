import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_SUMMON_STATE_TABLE = os.environ.get("USER_SUMMON_STATE_TABLE")
SUMMON_COOLDOWN_SECONDS = int(os.environ.get("SUMMON_COOLDOWN_SECONDS", "3600"))

MAX_CARDS_PER_SUMMON = 3

FILE_NAME_PATTERN = re.compile(r"^[a-z0-9_\-]+\.(jfif|jpg|jpeg|png|webp)$")

_serializer = TypeSerializer()

# Criado uma vez por container e reaproveitado entre invocações.
_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client("dynamodb")
    return _client


def response(status_code, body, headers=None):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, **(headers or {})},
        "body": json.dumps(body),
    }


def get_user_id(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub")


def parse_cards(body):
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError("Corpo da requisição inválido.") from error

    if not isinstance(body, dict):
        raise ValueError("Corpo da requisição inválido.")

    # Aceita {"cards": [...]} e o formato antigo {"card": {...}}.
    cards = body["cards"] if "cards" in body else [body.get("card", body)]

    if not isinstance(cards, list) or not 1 <= len(cards) <= MAX_CARDS_PER_SUMMON:
        raise ValueError("Quantidade de cartas inválida.")

    parsed = [parse_card(card) for card in cards]

    if len({card["file_name"] for card in parsed}) != len(parsed):
        raise ValueError("As cartas de uma invocação não podem se repetir.")

    return parsed


def parse_card(card):
    if not isinstance(card, dict):
        raise ValueError("Carta inválida.")

    name = card.get("name")
    rarity = card.get("rarity")
    file_name = card.get("file_name")

    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise ValueError("Nome da carta inválido.")

    if not isinstance(rarity, int) or isinstance(rarity, bool) or not 1 <= rarity <= 5:
        raise ValueError("Raridade da carta inválida.")

    if not isinstance(file_name, str) or not FILE_NAME_PATTERN.match(file_name):
        raise ValueError("Arquivo da carta inválido.")

    return {
        "name": name.strip(),
        "rarity": rarity,
        "file_name": file_name,
    }


def get_retry_after_seconds(user_id, now):
    result = get_client().get_item(
        TableName=USER_SUMMON_STATE_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    )
    last_summon_at = int(result.get("Item", {}).get("lastSummonAt", {}).get("N", "0"))
    return max(0, last_summon_at + SUMMON_COOLDOWN_SECONDS - now)


def is_cooldown_conflict(error):
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return False

    reasons = error.response.get("CancellationReasons") or []
    return bool(reasons) and reasons[0].get("Code") == "ConditionalCheckFailed"


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "Usuário não autenticado."})

    try:
        cards = parse_cards(event.get("body"))
    except ValueError as error:
        return response(400, {"message": str(error)})

    now = int(time.time())
    obtained_at = datetime.fromtimestamp(now, timezone.utc).isoformat()
    items = [
        {
            "userId": user_id,
            "ownedCardId": str(uuid.uuid4()),
            "obtainedAt": obtained_at,
            **card,
        }
        for card in cards
    ]

    try:
        # Registrar a invocação e guardar as cartas é atômico: se o usuário
        # ainda estiver no tempo de espera, nenhuma escrita acontece.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USER_SUMMON_STATE_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET lastSummonAt = :now",
                        "ConditionExpression": (
                            "attribute_not_exists(lastSummonAt) "
                            "OR lastSummonAt <= :threshold"
                        ),
                        "ExpressionAttributeValues": {
                            ":now": {"N": str(now)},
                            ":threshold": {"N": str(now - SUMMON_COOLDOWN_SECONDS)},
                        },
                    }
                },
                *(
                    {
                        "Put": {
                            "TableName": USER_CARDS_TABLE,
                            "Item": {
                                key: _serializer.serialize(value)
                                for key, value in item.items()
                            },
                        }
                    }
                    for item in items
                ),
            ]
        )
    except ClientError as error:
        if not is_cooldown_conflict(error):
            return response(500, {"message": "Não foi possível guardar as cartas."})

        try:
            retry_after = max(1, get_retry_after_seconds(user_id, now))
        except ClientError:
            retry_after = SUMMON_COOLDOWN_SECONDS

        return response(
            429,
            {
                "message": "Você ainda está no tempo de espera para invocar.",
                "retryAfterSeconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    return response(
        201,
        {"cards": items, "retryAfterSeconds": SUMMON_COOLDOWN_SECONDS},
    )
