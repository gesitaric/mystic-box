"""Leitura do mercado.

- `GET /shop/listings`: cartas à venda por outros jogadores (o anúncio mais
  barato de cada uma), ordens de compra de outros jogadores (a maior de cada
  carta, com o que o jogador receberia ao vender), os anúncios e ordens do
  próprio jogador, as cartas que podem ser pedidas e os limites.
- `GET /shop/history?fileName=`: últimas vendas da carta e um resumo.
"""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import (
    CHARACTERS,
    MARKET_FEE_PERCENT,
    MARKET_HISTORY_DAYS,
    MARKET_HISTORY_SIZE,
    MAX_ACTIVE_LISTINGS,
    MAX_ACTIVE_ORDERS,
    get_character,
    listing_price_range,
    market_fee,
    seller_proceeds,
)
from mystic_shared.market import summarize_sales

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

SHOP_LISTINGS_TABLE = os.environ.get("SHOP_LISTINGS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")
USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
BUY_ORDERS_TABLE = os.environ.get("BUY_ORDERS_TABLE")
MARKET_SALES_TABLE = os.environ.get("MARKET_SALES_TABLE")

HISTORY_ROUTE = "/shop/history"

MAX_FILE_NAME_LENGTH = 64

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


def scan_all(table):
    """Todos os itens da tabela (lê todas as páginas)."""
    items = []
    scan_kwargs = {"TableName": table, "ConsistentRead": True}
    while True:
        result = get_client().scan(**scan_kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        scan_kwargs["ExclusiveStartKey"] = last_key


def get_all_listings():
    """Todos os anúncios ativos (vendidos e cancelados saem da tabela)."""
    listings = []
    for item in scan_all(SHOP_LISTINGS_TABLE):
        character = get_character(item.get("file_name", {}).get("S"))
        if character is None:
            continue
        listings.append(
            {
                "listingId": item["listingId"]["S"],
                "sellerId": item["sellerId"]["S"],
                "price": int(item["price"]["N"]),
                "listedAt": item.get("listedAt", {}).get("S", ""),
                "character": character,
            }
        )
    return listings


def get_all_orders():
    """Todas as ordens de compra abertas (atendidas e canceladas saem da tabela)."""
    orders = []
    for item in scan_all(BUY_ORDERS_TABLE):
        character = get_character(item.get("file_name", {}).get("S"))
        if character is None:
            continue
        orders.append(
            {
                "orderId": item["orderId"]["S"],
                "buyerId": item["buyerId"]["S"],
                "price": int(item["price"]["N"]),
                "placedAt": item.get("placedAt", {}).get("S", ""),
                "character": character,
            }
        )
    return orders


def get_owned_counts(user_id):
    """{file_name: cópias na coleção do jogador}."""
    counts = {}
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "ProjectionExpression": "file_name",
        "ExpressionAttributeValues": {":userId": {"S": user_id}},
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        for item in result.get("Items", []):
            file_name = item.get("file_name", {}).get("S")
            if file_name:
                counts[file_name] = counts.get(file_name, 0) + 1
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return counts
        query_kwargs["ExclusiveStartKey"] = last_key


def market_cards(listings, balance):
    """Anúncios de outros jogadores agrupados por carta, do mais barato ao mais caro.

    Cada carta mostra o anúncio mais barato (é ele que se compra) e quantas
    cópias estão à venda.
    """
    groups = {}
    for listing in listings:
        groups.setdefault(listing["character"]["file_name"], []).append(listing)

    cards = []
    for group in groups.values():
        group.sort(key=lambda listing: (listing["price"], listing["listedAt"]))
        cheapest = group[0]
        character = cheapest["character"]
        cards.append(
            {
                "name": character["name"],
                "rarity": character["rarity"],
                "file_name": character["file_name"],
                "available": len(group),
                "listingId": cheapest["listingId"],
                "price": cheapest["price"],
                "canAfford": balance >= cheapest["price"],
            }
        )

    cards.sort(key=lambda card: (-card["rarity"], card["name"]))
    return cards


def own_listings(listings):
    """Anúncios do próprio jogador, do mais recente para o mais antigo."""
    mine = [
        {
            "listingId": listing["listingId"],
            "name": listing["character"]["name"],
            "rarity": listing["character"]["rarity"],
            "file_name": listing["character"]["file_name"],
            "price": listing["price"],
            "fee": market_fee(listing["price"]),
            "proceeds": seller_proceeds(listing["price"]),
            "listedAt": listing["listedAt"],
        }
        for listing in listings
    ]
    mine.sort(key=lambda listing: listing["listedAt"], reverse=True)
    return mine


def wanted_cards(orders, owned_counts):
    """Ordens de outros jogadores agrupadas por carta.

    Cada carta mostra a maior ordem (é para ela que se vende, a mais antiga no
    empate), quantas cópias são pedidas, quanto o jogador receberia (já sem a
    taxa) e se ele tem uma cópia para vender. As que ele pode atender vêm antes.
    """
    groups = {}
    for order in orders:
        groups.setdefault(order["character"]["file_name"], []).append(order)

    cards = []
    for group in groups.values():
        group.sort(key=lambda order: (-order["price"], order["placedAt"]))
        best = group[0]
        character = best["character"]
        owned = owned_counts.get(character["file_name"], 0)
        cards.append(
            {
                "name": character["name"],
                "rarity": character["rarity"],
                "file_name": character["file_name"],
                "wanted": len(group),
                "orderId": best["orderId"],
                "price": best["price"],
                "fee": market_fee(best["price"]),
                "proceeds": seller_proceeds(best["price"]),
                "owned": owned,
                "canFill": owned > 0,
            }
        )

    cards.sort(key=lambda card: (not card["canFill"], -card["rarity"], card["name"]))
    return cards


def own_orders(orders):
    """Ordens do próprio jogador, da mais recente para a mais antiga."""
    mine = [
        {
            "orderId": order["orderId"],
            "name": order["character"]["name"],
            "rarity": order["character"]["rarity"],
            "file_name": order["character"]["file_name"],
            "price": order["price"],
            "placedAt": order["placedAt"],
        }
        for order in orders
    ]
    mine.sort(key=lambda order: order["placedAt"], reverse=True)
    return mine


def order_options():
    """Cartas que podem ser pedidas, com a faixa de preço de cada uma."""
    options = [
        {
            "name": character["name"],
            "rarity": character["rarity"],
            "file_name": character["file_name"],
            "priceRange": listing_price_range(character),
        }
        for character in CHARACTERS
    ]
    options.sort(key=lambda option: (-option["rarity"], option["name"]))
    return options


def shop(user_id):
    try:
        balance = get_balance(user_id)
        listings = get_all_listings()
        orders = get_all_orders()
        owned_counts = get_owned_counts(user_id)
    except ClientError:
        return response(500, {"message": "Could not open the shop."})

    other_listings = [listing for listing in listings if listing["sellerId"] != user_id]
    my_listings = [listing for listing in listings if listing["sellerId"] == user_id]
    other_orders = [order for order in orders if order["buyerId"] != user_id]
    my_orders = own_orders([order for order in orders if order["buyerId"] == user_id])

    return response(
        200,
        {
            "cards": market_cards(other_listings, balance),
            "myListings": own_listings(my_listings),
            "maxActiveListings": MAX_ACTIVE_LISTINGS,
            "orders": wanted_cards(other_orders, owned_counts),
            "myOrders": my_orders,
            "reservedBalance": sum(order["price"] for order in my_orders),
            "maxActiveOrders": MAX_ACTIVE_ORDERS,
            "orderOptions": order_options(),
            "marketFeePercent": MARKET_FEE_PERCENT,
            "balance": balance,
        },
    )


def get_recent_sales(file_name):
    """Vendas da carta ainda no histórico, da mais recente para a mais antiga."""
    result = get_client().query(
        TableName=MARKET_SALES_TABLE,
        KeyConditionExpression="file_name = :fileName",
        # O TTL apaga com atraso: vendas vencidas ainda podem estar na tabela.
        FilterExpression="expiresAt > :now",
        ExpressionAttributeValues={
            ":fileName": {"S": file_name},
            ":now": {"N": str(int(time.time()))},
        },
        ScanIndexForward=False,
        Limit=MARKET_HISTORY_SIZE,
    )
    sales = sorted(
        result.get("Items", []), key=lambda item: item["saleId"]["S"], reverse=True
    )
    return [
        {"price": int(item["price"]["N"]), "soldAt": item.get("soldAt", {}).get("S", "")}
        for item in sales[:MARKET_HISTORY_SIZE]
    ]


def history(event):
    file_name = (event.get("queryStringParameters") or {}).get("fileName")
    if not isinstance(file_name, str) or not 0 < len(file_name) <= MAX_FILE_NAME_LENGTH:
        return response(400, {"message": "Choose a card."})
    character = get_character(file_name)
    if character is None:
        return response(404, {"message": "Unknown card."})

    try:
        sales = get_recent_sales(file_name)
    except ClientError:
        return response(500, {"message": "Could not load the price history."})

    return response(
        200,
        {
            "fileName": file_name,
            "name": character["name"],
            "rarity": character["rarity"],
            "days": MARKET_HISTORY_DAYS,
            "sales": sales,
            "summary": summarize_sales([sale["price"] for sale in sales]),
        },
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    if event.get("resource") == HISTORY_ROUTE:
        return history(event)
    return shop(user_id)
