"""GET /users/me/campaign: a campanha pelo mapa e o progresso do jogador.

Regiões, fases (inimigos, nível, experiência e recompensa calculados no
servidor), quais fases já foram vencidas e o epílogo das regiões completas.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.campaign import progress_from_item, public_campaign
from mystic_shared.progression import level_for_experience

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")

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


def get_item(table, user_id):
    return get_client().get_item(
        TableName=table,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        region_item = get_item(REGION_PROGRESS_TABLE, user_id)
        progress_item = get_item(USER_PROGRESS_TABLE, user_id) or {}
    except ClientError:
        return response(500, {"message": "Could not load the campaign."})

    experience = int(progress_item.get("experience", {}).get("N", "0"))
    level, _ = level_for_experience(experience)
    return response(
        200,
        {"regions": public_campaign(progress_from_item(region_item), level), "level": level},
    )
