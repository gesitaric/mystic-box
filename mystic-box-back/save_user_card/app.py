import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from mystic_shared import summon_token
from mystic_shared.cards import SUMMON_SIZE, get_character

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_SUMMON_STATE_TABLE = os.environ.get("USER_SUMMON_STATE_TABLE")
SUMMON_TOKENS_TABLE = os.environ.get("SUMMON_TOKENS_TABLE")
SUMMON_COOLDOWN_SECONDS = int(os.environ.get("SUMMON_COOLDOWN_SECONDS", "3600"))

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


def parse_summon(body):
    """Lê o token do sorteio e devolve (conteúdo do token, cartas sorteadas).

    O corpo só traz `summonToken`. Nome, raridade e imagem das cartas vêm das
    definições do servidor, nunca do cliente.
    """
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as error:
            raise summon_token.InvalidSummonToken("Invalid request body.") from error

    if not isinstance(body, dict):
        raise summon_token.InvalidSummonToken("Invalid request body.")

    payload = summon_token.verify(body.get("summonToken"))
    file_names = payload["cards"]

    if not 1 <= len(file_names) <= SUMMON_SIZE or len(set(file_names)) != len(file_names):
        raise summon_token.InvalidSummonToken("Invalid summon.")

    characters = [get_character(file_name) for file_name in file_names]
    if any(character is None for character in characters):
        raise summon_token.InvalidSummonToken("Invalid summon.")

    return payload, characters


def get_retry_after_seconds(user_id, now):
    result = get_client().get_item(
        TableName=USER_SUMMON_STATE_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    )
    last_summon_at = int(result.get("Item", {}).get("lastSummonAt", {}).get("N", "0"))
    return max(0, last_summon_at + SUMMON_COOLDOWN_SECONDS - now)


def get_failed_conditions(error):
    """Índices dos itens da transação cuja condição falhou."""
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return set()

    reasons = error.response.get("CancellationReasons") or []
    return {
        index
        for index, reason in enumerate(reasons)
        if reason.get("Code") == "ConditionalCheckFailed"
    }


# Posições na transação.
COOLDOWN_ITEM = 0
TOKEN_ITEM = 1


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        token, characters = parse_summon(event.get("body"))
    except summon_token.ExpiredSummonToken as error:
        return response(410, {"message": str(error)})
    except summon_token.InvalidSummonToken as error:
        return response(400, {"message": str(error)})
    except ClientError:
        return response(500, {"message": "Could not keep the cards."})

    now = int(time.time())
    obtained_at = datetime.fromtimestamp(now, timezone.utc).isoformat()
    items = [
        {
            "userId": user_id,
            "ownedCardId": str(uuid.uuid4()),
            "obtainedAt": obtained_at,
            "name": character["name"],
            "rarity": character["rarity"],
            "file_name": character["file_name"],
        }
        for character in characters
    ]

    try:
        # Registrar a invocação, gastar o token e guardar as cartas é atômico:
        # se o usuário estiver no tempo de espera ou o token já tiver sido
        # usado, nenhuma escrita acontece.
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
                {
                    "Put": {
                        "TableName": SUMMON_TOKENS_TABLE,
                        "Item": {
                            "tokenId": {"S": token["id"]},
                            "userId": {"S": user_id},
                            "usedAt": {"N": str(now)},
                            # TTL do DynamoDB: some depois que o token expira.
                            "expiresAt": {"N": str(token["exp"])},
                        },
                        "ConditionExpression": "attribute_not_exists(tokenId)",
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
        failed = get_failed_conditions(error)

        if TOKEN_ITEM in failed:
            return response(409, {"message": "These cards have already been kept."})

        if COOLDOWN_ITEM not in failed:
            return response(500, {"message": "Could not keep the cards."})

        try:
            retry_after = max(1, get_retry_after_seconds(user_id, now))
        except ClientError:
            retry_after = SUMMON_COOLDOWN_SECONDS

        return response(
            429,
            {
                "message": "You are still on cooldown for summoning.",
                "retryAfterSeconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    return response(
        201,
        {"cards": items, "retryAfterSeconds": SUMMON_COOLDOWN_SECONDS},
    )
