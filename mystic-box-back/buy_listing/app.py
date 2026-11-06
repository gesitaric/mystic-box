import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import get_character

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")
SHOP_LISTINGS_TABLE = os.environ.get("SHOP_LISTINGS_TABLE")

MAX_LISTING_ID_LENGTH = 64

# Posições na transação.
LISTING_ITEM = 0
BUYER_WALLET_ITEM = 1

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


def get_listing_id(event):
    listing_id = (event.get("pathParameters") or {}).get("listingId")
    if (
        not isinstance(listing_id, str)
        or not listing_id
        or len(listing_id) > MAX_LISTING_ID_LENGTH
    ):
        return None
    return listing_id


def get_listing(listing_id):
    result = get_client().get_item(
        TableName=SHOP_LISTINGS_TABLE,
        Key={"listingId": {"S": listing_id}},
        ConsistentRead=True,
    )
    item = result.get("Item")
    if not item:
        return None
    return {
        "listingId": item["listingId"]["S"],
        "sellerId": item["sellerId"]["S"],
        "file_name": item["file_name"]["S"],
        "price": int(item["price"]["N"]),
    }


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


def sold_out():
    return response(
        409, {"message": "This card was already sold or is no longer for sale."}
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    # Só o identificador do anúncio vem do cliente; preço, carta e vendedor são
    # lidos do anúncio gravado no servidor. Qualquer outro campo é ignorado.
    listing_id = get_listing_id(event)
    if not listing_id:
        return response(404, {"message": "Listing not found."})

    try:
        listing = get_listing(listing_id)
    except ClientError:
        return response(500, {"message": "Could not buy the card."})

    if listing is None:
        return sold_out()

    character = get_character(listing["file_name"])
    if character is None:
        return response(409, {"message": "This card cannot be bought."})

    if listing["sellerId"] == user_id:
        return response(409, {"message": "You cannot buy your own listing."})

    price = listing["price"]
    now = int(time.time())
    card = {
        "ownedCardId": str(uuid.uuid4()),
        "obtainedAt": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "name": character["name"],
        "rarity": character["rarity"],
        "file_name": character["file_name"],
    }

    try:
        # Tudo ou nada: o anúncio sai do mercado (só se ainda existir com o
        # mesmo preço e vendedor), o comprador paga (só se o saldo cobrir), o
        # vendedor recebe e a carta entra na coleção do comprador.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": SHOP_LISTINGS_TABLE,
                        "Key": {"listingId": {"S": listing_id}},
                        "ConditionExpression": (
                            "attribute_exists(listingId) AND sellerId = :seller "
                            "AND price = :price"
                        ),
                        "ExpressionAttributeValues": {
                            ":seller": {"S": listing["sellerId"]},
                            ":price": {"N": str(price)},
                        },
                    }
                },
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
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": listing["sellerId"]}},
                        "UpdateExpression": (
                            "ADD balance :price, activeListings :minusOne"
                        ),
                        "ExpressionAttributeValues": {
                            ":price": {"N": str(price)},
                            ":minusOne": {"N": "-1"},
                        },
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
        failed = get_failed_conditions(error)
        if LISTING_ITEM in failed:
            return sold_out()
        if BUYER_WALLET_ITEM in failed:
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

    return response(201, {"card": card, "price": price, "balance": balance})
