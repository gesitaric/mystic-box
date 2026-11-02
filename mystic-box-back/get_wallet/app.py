import json
import os

import boto3
from botocore.exceptions import ClientError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

# Moeda do jogo: Fragmentos Arcanos. Todo usuário começa com 0.
INITIAL_BALANCE = 0

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
            TableName=USER_WALLET_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        )
    except ClientError:
        return response(500, {"message": "Could not fetch the balance."})

    # Usuário sem registro na carteira ainda tem o saldo inicial.
    balance = int(
        result.get("Item", {}).get("balance", {}).get("N", str(INITIAL_BALANCE))
    )

    return response(200, {"balance": balance})
