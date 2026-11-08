import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.progression import level_for_experience
from mystic_shared.titles import title_name
from mystic_shared.usernames import (
    SEARCH_MAX_RESULTS,
    SEARCH_MIN_LENGTH,
    SEARCH_PARTITION,
    normalize_search,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
USERNAME_SEARCH_INDEX = "UsernameSearchIndex"

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


def get_titles(user_ids):
    """Nome do título escolhido por cada jogador encontrado (ou None)."""
    if not user_ids:
        return {}
    result = get_client().batch_get_item(
        RequestItems={
            USER_PROFILES_TABLE: {
                "Keys": [{"userId": {"S": user_id}} for user_id in user_ids],
                "ProjectionExpression": "userId, title",
            }
        }
    )
    return {
        item["userId"]["S"]: title_name(item.get("title", {}).get("S"))
        for item in result.get("Responses", {}).get(USER_PROFILES_TABLE, [])
    }


def get_levels(user_ids):
    """Nível de cada jogador encontrado (sem registro de progresso = nível 1)."""
    if not user_ids:
        return {}
    result = get_client().batch_get_item(
        RequestItems={
            USER_PROGRESS_TABLE: {
                "Keys": [{"userId": {"S": user_id}} for user_id in user_ids],
                "ProjectionExpression": "userId, experience",
            }
        }
    )
    experience = {
        item["userId"]["S"]: int(item.get("experience", {}).get("N", "0"))
        for item in result.get("Responses", {}).get(USER_PROGRESS_TABLE, [])
    }
    return {
        user_id: level_for_experience(experience.get(user_id, 0))[0]
        for user_id in user_ids
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    raw_query = (event.get("queryStringParameters") or {}).get("q")
    query = normalize_search(raw_query)
    if query is None:
        return response(
            400,
            {
                "message": (
                    f"Type at least {SEARCH_MIN_LENGTH} characters "
                    "(letters, numbers or _) to search."
                )
            },
        )

    try:
        # Só jogadores com nome definido entram no índice de busca.
        result = get_client().query(
            TableName=USER_PROFILES_TABLE,
            IndexName=USERNAME_SEARCH_INDEX,
            KeyConditionExpression="searchKey = :partition AND begins_with(usernameLower, :query)",
            ExpressionAttributeValues={
                ":partition": {"S": SEARCH_PARTITION},
                ":query": {"S": query},
            },
            Limit=SEARCH_MAX_RESULTS,
        )
        found = [
            (item["userId"]["S"], item["username"]["S"])
            for item in result.get("Items", [])
            if "username" in item
        ]
        levels = get_levels([found_id for found_id, _ in found])
        titles = get_titles([found_id for found_id, _ in found])
    except ClientError:
        return response(500, {"message": "Could not search for players."})

    return response(
        200,
        {
            "query": raw_query.strip(),
            "players": [
                {
                    "username": username,
                    "level": levels.get(found_id, 1),
                    "title": titles.get(found_id),
                    "isYou": found_id == user_id,
                }
                for found_id, username in found
            ],
        },
    )
