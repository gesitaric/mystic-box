import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import buy_price, shop_catalog

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

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


def get_balance(user_id):
    result = get_client().get_item(
        TableName=USER_WALLET_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    )
    return int(result.get("Item", {}).get("balance", {}).get("N", "0"))


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "Usuário não autenticado."})

    try:
        balance = get_balance(user_id)
    except ClientError:
        return response(500, {"message": "Não foi possível abrir a loja."})

    # Preço e se o jogador pode pagar são decididos aqui, não no cliente.
    cards = [
        {
            "name": character["name"],
            "rarity": character["rarity"],
            "file_name": character["file_name"],
            "buyPrice": buy_price(character),
            "canAfford": balance >= buy_price(character),
        }
        for character in shop_catalog()
    ]

    return response(200, {"cards": cards, "balance": balance})
