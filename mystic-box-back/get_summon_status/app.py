import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from mystic_shared import summon_token

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

USER_SUMMON_STATE_TABLE = os.environ.get("USER_SUMMON_STATE_TABLE")
SUMMON_COOLDOWN_SECONDS = int(os.environ.get("SUMMON_COOLDOWN_SECONDS", "3600"))

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


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        result = get_client().get_item(
            TableName=USER_SUMMON_STATE_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        )
        item = result.get("Item")
        now = int(time.time())
        # Sorteio aberto e ainda não guardado (ex.: em outro aparelho): o
        # frontend o guarda com o mesmo token.
        pending = summon_token.pending_summon(item, user_id, now)
    except ClientError:
        return response(500, {"message": "Could not fetch the cooldown."})

    last_summon_at = int((item or {}).get("lastSummonAt", {}).get("N", "0"))
    retry_after = max(0, last_summon_at + SUMMON_COOLDOWN_SECONDS - now)

    return response(
        200,
        {
            "retryAfterSeconds": retry_after,
            "cooldownSeconds": SUMMON_COOLDOWN_SECONDS,
            "pendingSummon": pending,
        },
    )
