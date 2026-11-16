"""Ordens de compra do mercado.

- `POST /shop/orders` `{"fileName", "price"}`: pede uma cópia da carta pelo
  preço (na faixa da raridade). Numa só transação: reserva os Fragmentos
  (debita o saldo, condição: cobre o preço e está abaixo do limite de ordens
  ativas) e grava a ordem.
- `POST /shop/orders/{orderId}/fill`: vende para a ordem uma cópia da coleção.
  Numa só transação: apaga a ordem (condição: ainda existe com o mesmo preço e
  comprador), tira a cópia mais recente do vendedor, põe a carta na coleção do
  comprador, credita o vendedor (preço menos a taxa), libera a vaga de ordem
  do comprador e registra a venda no histórico.
- `POST /shop/orders/{orderId}/cancel`: apaga a ordem e devolve os Fragmentos.

O cliente só manda a carta e o preço (ao pedir) ou o id da ordem; o resto é
lido aqui.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import (
    MAX_ACTIVE_ORDERS,
    get_character,
    is_valid_listing_price,
    listing_price_range,
    market_fee,
    seller_proceeds,
)
from mystic_shared.market import sale_record_put

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

BUY_ORDERS_TABLE = os.environ.get("BUY_ORDERS_TABLE")
SHOP_LISTINGS_TABLE = os.environ.get("SHOP_LISTINGS_TABLE")
USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")
MARKET_SALES_TABLE = os.environ.get("MARKET_SALES_TABLE")

CREATE_ROUTE = "/shop/orders"
FILL_ROUTE = "/shop/orders/{orderId}/fill"
CANCEL_ROUTE = "/shop/orders/{orderId}/cancel"

MAX_ID_LENGTH = 64

# Posições na transação de atender uma ordem.
FILL_ORDER_ITEM = 0
FILL_SELLER_CARD_ITEM = 1

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


def get_order_id(event):
    order_id = (event.get("pathParameters") or {}).get("orderId")
    if not isinstance(order_id, str) or not 0 < len(order_id) <= MAX_ID_LENGTH:
        return None
    return order_id


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


def get_balance_or_none(user_id):
    try:
        return get_balance(user_id)
    except ClientError:
        return None


def get_order(order_id):
    result = get_client().get_item(
        TableName=BUY_ORDERS_TABLE,
        Key={"orderId": {"S": order_id}},
        ConsistentRead=True,
    )
    item = result.get("Item")
    if not item:
        return None
    return {
        "orderId": item["orderId"]["S"],
        "buyerId": item["buyerId"]["S"],
        "file_name": item["file_name"]["S"],
        "price": int(item["price"]["N"]),
    }


def order_gone():
    return response(
        404, {"message": "This request was already filled or is no longer open."}
    )


# ------------------------------------------------------------ pedir ---


def parse_create(event):
    """(file_name, price) pedidos pelo cliente. Lança ValueError se inválidos."""
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, ValueError):
        raise ValueError("Invalid request body.")
    if not isinstance(body, dict):
        raise ValueError("Invalid request body.")

    file_name = body.get("fileName")
    if not isinstance(file_name, str) or not 0 < len(file_name) <= MAX_ID_LENGTH:
        raise ValueError("Invalid card.")

    price = body.get("price")
    if not isinstance(price, int) or isinstance(price, bool):
        raise ValueError("Invalid price.")

    return file_name, price


def cheapest_matching_listing(user_id, file_name, price):
    """Anúncio mais barato de outro jogador pela carta com preço <= `price`.

    Se existir, pedir por `price` seria pagar mais do que alguém já pede: o
    jogador deve comprar o anúncio. Devolve None se não houver.
    """
    cheapest = None
    scan_kwargs = {
        "TableName": SHOP_LISTINGS_TABLE,
        "FilterExpression": "file_name = :fileName AND sellerId <> :me AND price <= :price",
        "ExpressionAttributeValues": {
            ":fileName": {"S": file_name},
            ":me": {"S": user_id},
            ":price": {"N": str(price)},
        },
    }
    while True:
        result = get_client().scan(**scan_kwargs)
        for item in result.get("Items", []):
            listing = {"listingId": item["listingId"]["S"], "price": int(item["price"]["N"])}
            if cheapest is None or listing["price"] < cheapest["price"]:
                cheapest = listing
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return cheapest
        scan_kwargs["ExclusiveStartKey"] = last_key


def create_order(user_id, event):
    try:
        file_name, price = parse_create(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    character = get_character(file_name)
    if character is None:
        return response(409, {"message": "This card cannot be requested."})

    if not is_valid_listing_price(character, price):
        price_range = listing_price_range(character)
        return response(
            400,
            {
                "message": (
                    f"Price must be between {price_range['min']} and "
                    f"{price_range['max']} Arcane Shards for this card."
                ),
                "priceRange": price_range,
            },
        )

    try:
        listing = cheapest_matching_listing(user_id, file_name, price)
    except ClientError:
        return response(500, {"message": "Could not place the request."})

    if listing is not None:
        return response(
            409,
            {
                "message": (
                    f"This card is already on sale for {listing['price']} Arcane Shards. "
                    "Buy it in the shop instead."
                ),
                "listing": listing,
            },
        )

    placed_at = datetime.fromtimestamp(int(time.time()), timezone.utc).isoformat()
    order = {
        "orderId": str(uuid.uuid4()),
        "name": character["name"],
        "rarity": character["rarity"],
        "file_name": file_name,
        "price": price,
        "placedAt": placed_at,
    }

    try:
        # Os Fragmentos saem do saldo junto com a criação da ordem: ficam
        # reservados para quem vender e voltam se o jogador cancelar.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :minusPrice, activeOrders :one",
                        "ConditionExpression": (
                            "balance >= :price AND attribute_not_exists(activeOrders) "
                            "OR balance >= :price AND activeOrders < :max"
                        ),
                        "ExpressionAttributeValues": {
                            ":price": {"N": str(price)},
                            ":minusPrice": {"N": str(-price)},
                            ":one": {"N": "1"},
                            ":max": {"N": str(MAX_ACTIVE_ORDERS)},
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": BUY_ORDERS_TABLE,
                        "Item": {
                            "orderId": {"S": order["orderId"]},
                            "buyerId": {"S": user_id},
                            "file_name": {"S": file_name},
                            "name": {"S": character["name"]},
                            "rarity": {"N": str(character["rarity"])},
                            "price": {"N": str(price)},
                            "placedAt": {"S": placed_at},
                        },
                        "ConditionExpression": "attribute_not_exists(orderId)",
                    }
                },
            ]
        )
    except ClientError as error:
        if 0 not in get_failed_conditions(error):
            return response(500, {"message": "Could not place the request."})
        balance = get_balance_or_none(user_id)
        if balance is not None and balance < price:
            return response(
                409,
                {
                    "message": "Not enough Arcane Shards for this request.",
                    "price": price,
                    "balance": balance,
                },
            )
        return response(
            409,
            {
                "message": f"You can have at most {MAX_ACTIVE_ORDERS} open requests.",
                "maxActiveOrders": MAX_ACTIVE_ORDERS,
            },
        )

    return response(201, {"order": order, "balance": get_balance_or_none(user_id)})


# ---------------------------------------------------------- atender ---


def get_newest_copy(user_id, file_name):
    """ownedCardId da cópia mais recente da carta na coleção, ou None."""
    newest = None
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "FilterExpression": "file_name = :fileName",
        "ProjectionExpression": "ownedCardId, obtainedAt",
        "ExpressionAttributeValues": {
            ":userId": {"S": user_id},
            ":fileName": {"S": file_name},
        },
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        for item in result.get("Items", []):
            copy = (item.get("obtainedAt", {}).get("S", ""), item["ownedCardId"]["S"])
            if newest is None or copy > newest:
                newest = copy
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return newest[1] if newest else None
        query_kwargs["ExclusiveStartKey"] = last_key


def fill_order(user_id, event):
    order_id = get_order_id(event)
    if not order_id:
        return order_gone()

    try:
        order = get_order(order_id)
    except ClientError:
        return response(500, {"message": "Could not sell the card."})
    if order is None:
        return order_gone()
    if order["buyerId"] == user_id:
        return response(409, {"message": "You cannot sell to your own request."})

    character = get_character(order["file_name"])
    if character is None:
        return response(409, {"message": "This card cannot be sold."})

    try:
        owned_card_id = get_newest_copy(user_id, order["file_name"])
    except ClientError:
        return response(500, {"message": "Could not sell the card."})
    if owned_card_id is None:
        return response(409, {"message": "You have no copy of this card to sell."})

    price = order["price"]
    proceeds = seller_proceeds(price)
    now = int(time.time())
    sold_at = datetime.fromtimestamp(now, timezone.utc).isoformat()
    file_name = character["file_name"]

    try:
        # Os Fragmentos do comprador já estão reservados desde que ele pediu.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": BUY_ORDERS_TABLE,
                        "Key": {"orderId": {"S": order_id}},
                        "ConditionExpression": (
                            "attribute_exists(orderId) AND buyerId = :buyer "
                            "AND price = :price"
                        ),
                        "ExpressionAttributeValues": {
                            ":buyer": {"S": order["buyerId"]},
                            ":price": {"N": str(price)},
                        },
                    }
                },
                {
                    "Delete": {
                        "TableName": USER_CARDS_TABLE,
                        "Key": {
                            "userId": {"S": user_id},
                            "ownedCardId": {"S": owned_card_id},
                        },
                        "ConditionExpression": (
                            "attribute_exists(ownedCardId) AND file_name = :fileName"
                        ),
                        "ExpressionAttributeValues": {":fileName": {"S": file_name}},
                    }
                },
                {
                    "Put": {
                        "TableName": USER_CARDS_TABLE,
                        "Item": {
                            "userId": {"S": order["buyerId"]},
                            "ownedCardId": {"S": str(uuid.uuid4())},
                            "obtainedAt": {"S": sold_at},
                            "name": {"S": character["name"]},
                            "rarity": {"N": str(character["rarity"])},
                            "file_name": {"S": file_name},
                        },
                        "ConditionExpression": "attribute_not_exists(ownedCardId)",
                    }
                },
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :proceeds",
                        "ExpressionAttributeValues": {":proceeds": {"N": str(proceeds)}},
                    }
                },
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": order["buyerId"]}},
                        "UpdateExpression": "ADD activeOrders :minusOne",
                        "ExpressionAttributeValues": {":minusOne": {"N": "-1"}},
                    }
                },
                sale_record_put(MARKET_SALES_TABLE, file_name, price, sold_at, order_id, now),
            ]
        )
    except ClientError as error:
        failed = get_failed_conditions(error)
        if FILL_ORDER_ITEM in failed:
            return order_gone()
        if FILL_SELLER_CARD_ITEM in failed:
            return response(
                409,
                {"message": "Your collection changed. Nothing was sold; please try again."},
            )
        return response(500, {"message": "Could not sell the card."})

    return response(
        200,
        {
            "orderId": order_id,
            "name": character["name"],
            "file_name": file_name,
            "price": price,
            "fee": market_fee(price),
            "proceeds": proceeds,
            "balance": get_balance_or_none(user_id),
        },
    )


# --------------------------------------------------------- cancelar ---


def cancel_order(user_id, event):
    order_id = get_order_id(event)
    if not order_id:
        return order_gone()

    try:
        order = get_order(order_id)
    except ClientError:
        return response(500, {"message": "Could not cancel the request."})
    # Ordem de outro jogador é tratada como inexistente.
    if order is None or order["buyerId"] != user_id:
        return order_gone()

    try:
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": BUY_ORDERS_TABLE,
                        "Key": {"orderId": {"S": order_id}},
                        "ConditionExpression": "attribute_exists(orderId) AND buyerId = :me",
                        "ExpressionAttributeValues": {":me": {"S": user_id}},
                    }
                },
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :price, activeOrders :minusOne",
                        "ExpressionAttributeValues": {
                            ":price": {"N": str(order["price"])},
                            ":minusOne": {"N": "-1"},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        if get_failed_conditions(error):
            return order_gone()
        return response(500, {"message": "Could not cancel the request."})

    return response(
        200,
        {
            "orderId": order_id,
            "refunded": order["price"],
            "balance": get_balance_or_none(user_id),
        },
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    resource = event.get("resource")
    if event.get("httpMethod") == "POST":
        if resource == CREATE_ROUTE:
            return create_order(user_id, event)
        if resource == FILL_ROUTE:
            return fill_order(user_id, event)
        if resource == CANCEL_ROUTE:
            return cancel_order(user_id, event)
    return response(404, {"message": "Not found."})
