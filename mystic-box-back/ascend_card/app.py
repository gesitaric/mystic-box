"""POST /users/me/cards/ascend: consome cópias repetidas para subir a ascensão.

O cliente manda só `fileName`. Quantas cópias custa, se o jogador pode subir e
o que muda na carta são decididos aqui (`mystic_shared.ascension`). Numa só
transação: apaga as cópias consumidas (as mais recentes), confere que a cópia
mantida continua na coleção e grava a nova ascensão (condição: ainda é a que
foi lida).
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.ascension import (
    MAX_ASCENSION,
    clamp_ascension,
    next_ascension_cost,
    public_ascension,
)
from mystic_shared.battle import ascension_unlocks_skill, public_skills
from mystic_shared.cards import get_character
from mystic_shared.lore import unlocked_secret_title
from mystic_shared.stats import public_battle_profile

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
CARD_ASCENSIONS_TABLE = os.environ.get("CARD_ASCENSIONS_TABLE")

MAX_FILE_NAME_LENGTH = 64

# Criado uma vez por container e reaproveitado entre invocações.
_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client("dynamodb")
    return _client


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def get_user_id(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub")


def parse_file_name(event):
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, ValueError):
        raise ValueError("Invalid request body.")
    if not isinstance(body, dict):
        raise ValueError("Invalid request body.")

    file_name = body.get("fileName")
    if (
        not isinstance(file_name, str)
        or not file_name
        or len(file_name) > MAX_FILE_NAME_LENGTH
    ):
        raise ValueError("Invalid card.")
    return file_name


def get_ascension(user_id, file_name):
    """(ascensão atual, se já existe registro)."""
    item = get_client().get_item(
        TableName=CARD_ASCENSIONS_TABLE,
        Key={"userId": {"S": user_id}, "file_name": {"S": file_name}},
        ConsistentRead=True,
    ).get("Item")
    if not item:
        return 0, False
    return clamp_ascension(item.get("ascension", {}).get("N", "0")), True


def get_owned_copies(user_id, file_name):
    """Cópias da carta na coleção, da mais recente para a mais antiga."""
    copies = []
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "FilterExpression": "file_name = :fileName",
        "ProjectionExpression": "ownedCardId, obtainedAt",
        "ExpressionAttributeValues": {
            ":userId": {"S": user_id},
            ":fileName": {"S": file_name},
        },
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        copies.extend(
            {
                "ownedCardId": item["ownedCardId"]["S"],
                "obtainedAt": item.get("obtainedAt", {}).get("S", ""),
            }
            for item in result.get("Items", [])
        )
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    copies.sort(key=lambda copy: copy["obtainedAt"], reverse=True)
    return copies


def copy_key(user_id, copy):
    return {"userId": {"S": user_id}, "ownedCardId": {"S": copy["ownedCardId"]}}


def ascend(user_id, file_name, current, exists, copies, cost):
    """Transação: consome `cost` cópias, mantém uma e grava a nova ascensão."""
    consumed, kept = copies[:cost], copies[cost]
    owned_condition = {
        "ConditionExpression": "attribute_exists(ownedCardId) AND file_name = :fileName",
        "ExpressionAttributeValues": {":fileName": {"S": file_name}},
    }
    if exists:
        ascension_condition = {
            "ConditionExpression": "ascension = :current",
            "ExpressionAttributeValues": {":current": {"N": str(current)}},
        }
    else:
        ascension_condition = {"ConditionExpression": "attribute_not_exists(userId)"}

    updated_at = datetime.fromtimestamp(int(time.time()), timezone.utc).isoformat()
    get_client().transact_write_items(
        TransactItems=[
            *(
                {
                    "Delete": {
                        "TableName": USER_CARDS_TABLE,
                        "Key": copy_key(user_id, copy),
                        **owned_condition,
                    }
                }
                for copy in consumed
            ),
            # A cópia que fica não pode ter saído (anunciada) ao mesmo tempo.
            {
                "ConditionCheck": {
                    "TableName": USER_CARDS_TABLE,
                    "Key": copy_key(user_id, kept),
                    **owned_condition,
                }
            },
            {
                "Put": {
                    "TableName": CARD_ASCENSIONS_TABLE,
                    "Item": {
                        "userId": {"S": user_id},
                        "file_name": {"S": file_name},
                        "ascension": {"N": str(current + 1)},
                        "updatedAt": {"S": updated_at},
                    },
                    **ascension_condition,
                }
            },
        ]
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        file_name = parse_file_name(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    character = get_character(file_name)
    if not character:
        return response(409, {"message": "This card cannot ascend."})
    name = character["name"]

    try:
        current, exists = get_ascension(user_id, file_name)
        copies = get_owned_copies(user_id, file_name)
    except ClientError:
        return response(500, {"message": "Could not ascend the card."})

    if not copies:
        return response(404, {"message": "Card not found in your collection."})

    cost = next_ascension_cost(current)
    if cost is None:
        return response(
            409, {"message": f"{name} is already at max ascension ({MAX_ASCENSION})."}
        )
    if len(copies) < cost + 1:
        return response(
            409,
            {
                "message": (
                    f"You need {cost + 1} copies of {name} to ascend "
                    f"(you have {len(copies)}). One copy always stays in your collection."
                ),
                "required": cost + 1,
                "available": len(copies),
            },
        )

    try:
        ascend(user_id, file_name, current, exists, copies, cost)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            return response(
                409,
                {
                    "message": (
                        "Your collection changed while ascending. Nothing was "
                        "consumed; please try again."
                    )
                },
            )
        return response(500, {"message": "Could not ascend the card."})

    ascension = current + 1
    remaining = len(copies) - cost
    return response(
        200,
        {
            "fileName": file_name,
            "name": name,
            "consumed": cost,
            "quantity": remaining,
            "ascension": public_ascension(
                ascension, remaining, ascension_unlocks_skill(character)
            ),
            "battle": {
                **public_battle_profile(character, ascension=ascension),
                "skills": public_skills(character, ascension),
            },
            # Título do capítulo secreto liberado nesta ascensão, ou None.
            "secretUnlocked": unlocked_secret_title(character, current, ascension),
        },
    )
