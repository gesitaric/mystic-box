import json
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")

# Criado uma vez por container e reaproveitado entre invocações.
table = boto3.resource("dynamodb").Table(USER_CARDS_TABLE)


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


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "Usuário não autenticado."})

    try:
        items = []
        query_kwargs = {
            "KeyConditionExpression": Key("userId").eq(user_id),
        }

        while True:
            result = table.query(**query_kwargs)
            items.extend(result.get("Items", []))

            last_key = result.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
    except ClientError:
        return response(500, {"message": "Não foi possível buscar suas cartas."})

    cards = [
        {
            "ownedCardId": item.get("ownedCardId"),
            "name": item.get("name"),
            "rarity": int(item["rarity"]) if item.get("rarity") is not None else None,
            "file_name": item.get("file_name"),
            "obtainedAt": item.get("obtainedAt"),
        }
        for item in items
    ]
    cards.sort(key=lambda card: card.get("obtainedAt") or "", reverse=True)

    return response(200, {"cards": cards})
