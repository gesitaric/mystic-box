import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from mystic_shared.usernames import (
    SEARCH_PARTITION,
    USERNAME_CHANGE_COOLDOWN_DAYS,
    USERNAME_CHANGE_COOLDOWN_SECONDS,
    change_status,
    normalize,
    validate_username,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")
USERNAMES_TABLE = os.environ.get("USERNAMES_TABLE")

# Posições na transação.
PROFILE_ITEM = 0
RESERVATION_ITEM = 1

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


def parse_body(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return None
    return body if isinstance(body, dict) else None


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


def cooldown_response(changed_at, now):
    status = change_status(changed_at, now)
    return response(
        429,
        {
            "message": (
                "You can only change your username once every "
                f"{USERNAME_CHANGE_COOLDOWN_DAYS} days."
            ),
            "usernameChange": status,
            "retryAfterSeconds": status["retryAfterSeconds"],
        },
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    body = parse_body(event)
    if body is None:
        return response(400, {"message": "Invalid request body."})

    username, error_message = validate_username(body.get("username"))
    if error_message:
        return response(400, {"message": error_message})
    username_lower = normalize(username)

    try:
        profile = get_client().get_item(
            TableName=USER_PROFILES_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        ).get("Item", {})
    except ClientError:
        return response(500, {"message": "Could not change your username."})

    old_username = profile.get("username", {}).get("S")
    old_lower = profile.get("usernameLower", {}).get("S")
    changed_at = profile.get("usernameChangedAt", {}).get("N")

    if old_username == username:
        return response(400, {"message": "That is already your username."})

    now = int(time.time())
    if not change_status(changed_at, now)["canChange"]:
        return cooldown_response(changed_at, now)

    # A condição no perfil repete a checagem do tempo de espera e garante que
    # o nome antigo não mudou desde a leitura (duas trocas ao mesmo tempo).
    if old_lower:
        profile_condition = "usernameLower = :oldLower AND usernameChangedAt <= :cutoff"
        condition_values = {
            ":oldLower": {"S": old_lower},
            ":cutoff": {"N": str(now - USERNAME_CHANGE_COOLDOWN_SECONDS)},
        }
    else:
        profile_condition = "attribute_not_exists(usernameLower)"
        condition_values = {}

    transact_items = [
        {
            "Update": {
                "TableName": USER_PROFILES_TABLE,
                "Key": {"userId": {"S": user_id}},
                "UpdateExpression": (
                    "SET username = :username, usernameLower = :lower, "
                    "usernameChangedAt = :now, searchKey = :partition"
                ),
                "ConditionExpression": profile_condition,
                "ExpressionAttributeValues": {
                    ":username": {"S": username},
                    ":lower": {"S": username_lower},
                    ":now": {"N": str(now)},
                    ":partition": {"S": SEARCH_PARTITION},
                    **condition_values,
                },
            }
        },
        {
            # Reserva o nome (sem diferenciar maiúsculas): só um jogador por nome.
            # O próprio dono pode regravar, ex.: trocar só maiúsculas/minúsculas.
            "Put": {
                "TableName": USERNAMES_TABLE,
                "Item": {
                    "usernameLower": {"S": username_lower},
                    "userId": {"S": user_id},
                },
                "ConditionExpression": "attribute_not_exists(usernameLower) OR userId = :me",
                "ExpressionAttributeValues": {":me": {"S": user_id}},
            }
        },
    ]
    if old_lower and old_lower != username_lower:
        # Libera o nome antigo.
        transact_items.append(
            {
                "Delete": {
                    "TableName": USERNAMES_TABLE,
                    "Key": {"usernameLower": {"S": old_lower}},
                    "ConditionExpression": "userId = :me",
                    "ExpressionAttributeValues": {":me": {"S": user_id}},
                }
            }
        )

    try:
        get_client().transact_write_items(TransactItems=transact_items)
    except ClientError as error:
        failed = get_failed_conditions(error)
        if RESERVATION_ITEM in failed:
            return response(409, {"message": "This username is already taken."})
        if PROFILE_ITEM in failed:
            return response(
                409,
                {"message": "Your username was changed at the same time. Reload and try again."},
            )
        return response(500, {"message": "Could not change your username."})

    return response(
        200,
        {
            "username": username,
            "usernameChange": change_status(now, now),
        },
    )
