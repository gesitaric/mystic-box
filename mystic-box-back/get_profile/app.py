import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from mystic_shared.progression import public_progress
from mystic_shared.titles import load_earned_titles, public_titles, title_name
from mystic_shared.usernames import change_status, public_rules

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")
REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")
CARD_ASCENSIONS_TABLE = os.environ.get("CARD_ASCENSIONS_TABLE")

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
            TableName=USER_PROGRESS_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        )
        profile = get_client().get_item(
            TableName=USER_PROFILES_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        ).get("Item", {})
        _, earned = load_earned_titles(
            get_client(), user_id, USER_PROGRESS_TABLE, REGION_PROGRESS_TABLE,
            CARD_ASCENSIONS_TABLE,
        )
    except ClientError:
        return response(500, {"message": "Could not load your profile."})

    # Usuário sem registro ainda está no nível 1, sem experiência.
    item = result.get("Item", {})
    progress = public_progress(
        int(item.get("experience", {}).get("N", "0")),
        wins=int(item.get("wins", {}).get("N", "0")),
        losses=int(item.get("losses", {}).get("N", "0")),
    )

    # Sem nome definido, o jogador é identificado pelo id do Cognito.
    username = profile.get("username", {}).get("S")
    changed_at = profile.get("usernameChangedAt", {}).get("N")
    return response(
        200,
        {
            **progress,
            "userId": user_id,
            "username": username,
            "usernameChange": change_status(changed_at, time.time()),
            "usernameRules": public_rules(),
            # Título escolhido (conferido ao escolher) e todos os títulos.
            "title": (
                {"id": profile["title"]["S"], "name": title_name(profile["title"]["S"])}
                if title_name(profile.get("title", {}).get("S"))
                else None
            ),
            "titles": public_titles(earned),
        },
    )
