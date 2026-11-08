"""POST /users/me/regions/claim: recompensa por completar a coleção de uma região.

O cliente manda só `regionId`. A coleção é lida aqui e a recompensa vem de
`mystic_shared.mastery`. Numa só transação: marca a região como recebida
(condição: ainda não recebida) e soma os Fragmentos ao saldo.
"""

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.mastery import (
    claim_attribute,
    collection_reward,
    is_complete,
    regions_with_residents,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

MAX_ID_LENGTH = 64

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


def get_owned_file_names(user_id):
    names = set()
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "ProjectionExpression": "file_name",
        "ExpressionAttributeValues": {":userId": {"S": user_id}},
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        names.update(
            item["file_name"]["S"] for item in result.get("Items", []) if "file_name" in item
        )
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return names
        query_kwargs["ExclusiveStartKey"] = last_key


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, ValueError):
        body = None
    region_id = body.get("regionId") if isinstance(body, dict) else None
    if not isinstance(region_id, str) or not 0 < len(region_id) <= MAX_ID_LENGTH:
        return response(400, {"message": "Choose a region."})
    if region_id not in regions_with_residents():
        return response(404, {"message": "Unknown region."})

    try:
        owned = get_owned_file_names(user_id)
    except ClientError:
        return response(500, {"message": "Could not claim the reward."})
    if not is_complete(region_id, owned):
        return response(409, {"message": "Summon every champion of this land first."})

    reward = collection_reward(region_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": REGION_PROGRESS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET #claimed = :now",
                        # Recompensa única: só grava se ainda não recebeu.
                        "ConditionExpression": "attribute_not_exists(#claimed)",
                        "ExpressionAttributeNames": {"#claimed": claim_attribute(region_id)},
                        "ExpressionAttributeValues": {":now": {"S": now}},
                    }
                },
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :reward",
                        "ExpressionAttributeValues": {":reward": {"N": str(reward)}},
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            return response(409, {"message": "You already claimed this reward."})
        return response(500, {"message": "Could not claim the reward."})

    return response(200, {"region": region_id, "reward": reward, "claimed": True})
