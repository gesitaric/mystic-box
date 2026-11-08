"""POST /users/me/title: escolhe o título mostrado no perfil.

O cliente manda só `titleId` (ou null para tirar o título). O servidor confere
se o jogador conquistou o título (`mystic_shared.titles`) antes de gravar.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.titles import get_title, load_earned_titles

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")
CARD_ASCENSIONS_TABLE = os.environ.get("CARD_ASCENSIONS_TABLE")

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
    if not isinstance(body, dict) or "titleId" not in body:
        return response(400, {"message": "Choose a title."})
    title_id = body["titleId"]

    if title_id is None:
        update = {"UpdateExpression": "REMOVE title"}
    else:
        if not isinstance(title_id, str) or not 0 < len(title_id) <= MAX_ID_LENGTH:
            return response(400, {"message": "Choose a title."})
        title = get_title(title_id)
        if not title:
            return response(404, {"message": "Unknown title."})
        try:
            _, earned = load_earned_titles(
                get_client(), user_id, USER_PROGRESS_TABLE, REGION_PROGRESS_TABLE,
                CARD_ASCENSIONS_TABLE,
            )
        except ClientError:
            return response(500, {"message": "Could not change your title."})
        if title_id not in earned:
            return response(409, {"message": "You have not earned this title yet."})
        update = {
            "UpdateExpression": "SET title = :title",
            "ExpressionAttributeValues": {":title": {"S": title_id}},
        }

    try:
        get_client().update_item(
            TableName=USER_PROFILES_TABLE, Key={"userId": {"S": user_id}}, **update
        )
    except ClientError:
        return response(500, {"message": "Could not change your title."})

    return response(
        200,
        {"title": {"id": title_id, "name": get_title(title_id)["name"]} if title_id else None},
    )
