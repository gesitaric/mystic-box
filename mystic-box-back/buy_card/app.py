import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import buy_price, get_character, sell_price, shop_catalog

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

MAX_FILE_NAME_LENGTH = 64

# Posições na transação.
WALLET_ITEM = 0

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


def get_shop_character(event):
    """Carta da loja indicada no caminho, ou None se não estiver à venda."""
    file_name = (event.get("pathParameters") or {}).get("fileName")
    if (
        not isinstance(file_name, str)
        or not file_name
        or len(file_name) > MAX_FILE_NAME_LENGTH
    ):
        return None

    character = get_character(file_name)
    if character is None or character not in shop_catalog():
        return None
    return character


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
        return response(401, {"message": "User is not authenticated."})

    # Só o identificador da carta vem do cliente; nome, raridade e preço são
    # lidos das definições do servidor. Qualquer outro campo é ignorado.
    character = get_shop_character(event)
    if not character:
        return response(404, {"message": "This card is not for sale."})

    price = buy_price(character)
    now = int(time.time())
    card = {
        "ownedCardId": str(uuid.uuid4()),
        "obtainedAt": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "name": character["name"],
        "rarity": character["rarity"],
        "file_name": character["file_name"],
    }

    try:
        # Debitar e entregar a carta é atômico. A condição no saldo impede
        # gastar mais do que se tem, mesmo com compras simultâneas.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET balance = balance - :price",
                        "ConditionExpression": "balance >= :price",
                        "ExpressionAttributeValues": {":price": {"N": str(price)}},
                    }
                },
                {
                    "Put": {
                        "TableName": USER_CARDS_TABLE,
                        "Item": {
                            "userId": {"S": user_id},
                            "ownedCardId": {"S": card["ownedCardId"]},
                            "obtainedAt": {"S": card["obtainedAt"]},
                            "name": {"S": card["name"]},
                            "rarity": {"N": str(card["rarity"])},
                            "file_name": {"S": card["file_name"]},
                        },
                        "ConditionExpression": "attribute_not_exists(ownedCardId)",
                    }
                },
            ]
        )
    except ClientError as error:
        if WALLET_ITEM in get_failed_conditions(error):
            try:
                balance = get_balance(user_id)
            except ClientError:
                balance = None
            return response(
                409,
                {
                    "message": "Not enough Arcane Shards for this purchase.",
                    "price": price,
                    "balance": balance,
                },
            )
        return response(500, {"message": "Could not buy the card."})

    try:
        balance = get_balance(user_id)
    except ClientError:
        # A compra já aconteceu; o cliente consulta o saldo depois.
        balance = None

    return response(
        201,
        {
            "card": {**card, "sellPrice": sell_price(character)},
            "price": price,
            "balance": balance,
        },
    )
