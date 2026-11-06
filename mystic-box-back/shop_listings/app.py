import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import MAX_ACTIVE_LISTINGS, get_character

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

SHOP_LISTINGS_TABLE = os.environ.get("SHOP_LISTINGS_TABLE")
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


def get_all_listings():
    """Todos os anúncios ativos (vendidos e cancelados saem da tabela)."""
    listings = []
    scan_kwargs = {"TableName": SHOP_LISTINGS_TABLE, "ConsistentRead": True}

    while True:
        result = get_client().scan(**scan_kwargs)
        for item in result.get("Items", []):
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

        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return listings


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
            "listedAt": listing["listedAt"],
        }
        for listing in listings
    ]
    mine.sort(key=lambda listing: listing["listedAt"], reverse=True)
    return mine


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        balance = get_balance(user_id)
        listings = get_all_listings()
    except ClientError:
        return response(500, {"message": "Could not open the shop."})

    others = [listing for listing in listings if listing["sellerId"] != user_id]
    mine = [listing for listing in listings if listing["sellerId"] == user_id]

    return response(
        200,
        {
            "cards": market_cards(others, balance),
            "myListings": own_listings(mine),
            "maxActiveListings": MAX_ACTIVE_LISTINGS,
            "balance": balance,
        },
    )
