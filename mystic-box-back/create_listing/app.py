import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import (
    MAX_ACTIVE_LISTINGS,
    MAX_LISTING_QUANTITY,
    get_character,
    is_valid_listing_price,
    listing_price_range,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")
SHOP_LISTINGS_TABLE = os.environ.get("SHOP_LISTINGS_TABLE")

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


def parse_request(event):
    """(file_name, quantity, price) pedidos pelo cliente. Lança ValueError se inválidos.

    O cliente diz QUAL carta, QUANTAS cópias e o preço que quer pedir; se o
    preço é aceito e quais cópias saem da coleção é decidido aqui.
    """
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, ValueError):
        raise ValueError("Invalid request body.")
    if not isinstance(body, dict):
        raise ValueError("Invalid request body.")

    file_name = body.get("fileName")
    if (
        not isinstance(file_name, str)
        or not file_name
        or len(file_name) > MAX_FILE_NAME_LENGTH
    ):
        raise ValueError("Invalid card.")

    quantity = body.get("quantity")
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or not 1 <= quantity <= MAX_LISTING_QUANTITY
    ):
        raise ValueError(
            f"Invalid quantity. Choose from 1 to {MAX_LISTING_QUANTITY} copies."
        )

    price = body.get("price")
    if not isinstance(price, int) or isinstance(price, bool):
        raise ValueError("Invalid price.")

    return file_name, quantity, price


def get_owned_copies(user_id, file_name):
    """Cópias da carta na coleção do usuário, da mais recente para a mais antiga."""
    copies = []
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
        copies.extend(
            {
                "ownedCardId": item["ownedCardId"]["S"],
                "obtainedAt": item.get("obtainedAt", {}).get("S", ""),
            }
            for item in result.get("Items", [])
        )

        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    copies.sort(key=lambda copy: copy["obtainedAt"], reverse=True)
    return copies


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


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        file_name, quantity, price = parse_request(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    # Nome e raridade vêm SEMPRE das definições do servidor.
    character = get_character(file_name)
    if not character:
        return response(409, {"message": "This card cannot be listed."})

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
        copies = get_owned_copies(user_id, file_name)
    except ClientError:
        return response(500, {"message": "Could not list the card."})

    if not copies:
        return response(404, {"message": "Card not found in your collection."})

    if quantity > len(copies):
        return response(
            409,
            {
                "message": f"You only have {len(copies)} copy(ies) of this card.",
                "available": len(copies),
            },
        )

    # Anuncia as cópias mais recentes e mantém as mais antigas na coleção.
    listed_copies = copies[:quantity]
    listed_at = datetime.fromtimestamp(int(time.time()), timezone.utc).isoformat()
    listings = [
        {"listingId": str(uuid.uuid4()), **copy} for copy in listed_copies
    ]

    try:
        # A cópia sai da coleção e entra no mercado na mesma transação: ela
        # não pode ser anunciada duas vezes nem usada enquanto está à venda.
        # O contador na carteira limita os anúncios ativos do jogador.
        get_client().transact_write_items(
            TransactItems=[
                *(
                    {
                        "Delete": {
                            "TableName": USER_CARDS_TABLE,
                            "Key": {
                                "userId": {"S": user_id},
                                "ownedCardId": {"S": listing["ownedCardId"]},
                            },
                            "ConditionExpression": (
                                "attribute_exists(ownedCardId) AND file_name = :fileName"
                            ),
                            "ExpressionAttributeValues": {
                                ":fileName": {"S": file_name}
                            },
                        }
                    }
                    for listing in listings
                ),
                *(
                    {
                        "Put": {
                            "TableName": SHOP_LISTINGS_TABLE,
                            "Item": {
                                "listingId": {"S": listing["listingId"]},
                                "sellerId": {"S": user_id},
                                "ownedCardId": {"S": listing["ownedCardId"]},
                                "obtainedAt": {"S": listing["obtainedAt"]},
                                "name": {"S": character["name"]},
                                "rarity": {"N": str(character["rarity"])},
                                "file_name": {"S": file_name},
                                "price": {"N": str(price)},
                                "listedAt": {"S": listed_at},
                            },
                            "ConditionExpression": "attribute_not_exists(listingId)",
                        }
                    }
                    for listing in listings
                ),
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD activeListings :quantity",
                        "ConditionExpression": (
                            "attribute_not_exists(activeListings) "
                            "OR activeListings <= :limit"
                        ),
                        "ExpressionAttributeValues": {
                            ":quantity": {"N": str(quantity)},
                            ":limit": {"N": str(MAX_ACTIVE_LISTINGS - quantity)},
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        failed = get_failed_conditions(error)
        if 2 * quantity in failed:
            return response(
                409,
                {
                    "message": (
                        f"You can have at most {MAX_ACTIVE_LISTINGS} cards for sale "
                        "at the same time."
                    ),
                    "maxActiveListings": MAX_ACTIVE_LISTINGS,
                },
            )
        if failed:
            return response(
                409,
                {
                    "message": (
                        "Your collection changed while listing. Nothing was listed; "
                        "please try again."
                    )
                },
            )
        return response(500, {"message": "Could not list the card."})

    return response(
        201,
        {
            "fileName": file_name,
            "name": character["name"],
            "listedQuantity": quantity,
            "listingIds": [listing["listingId"] for listing in listings],
            "remainingQuantity": len(copies) - quantity,
            "price": price,
        },
    )
