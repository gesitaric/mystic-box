import json
import os
import time
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
    return result.get("Item")


def is_condition_failure(error):
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return False

    reasons = error.response.get("CancellationReasons") or []
    return any(reason.get("Code") == "ConditionalCheckFailed" for reason in reasons)


def not_found():
    return response(
        404, {"message": "This listing was already sold or is no longer for sale."}
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    listing_id = get_listing_id(event)
    if not listing_id:
        return not_found()

    try:
        item = get_listing(listing_id)
    except ClientError:
        return response(500, {"message": "Could not cancel the listing."})

    # Anúncio de outro jogador é tratado como inexistente.
    if not item or item["sellerId"]["S"] != user_id:
        return not_found()

    file_name = item["file_name"]["S"]
    character = get_character(file_name)
    if character is None:
        return response(409, {"message": "This listing cannot be cancelled."})

    # A carta volta para a coleção com o mesmo id e data de obtenção.
    owned_card_id = item["ownedCardId"]["S"]
    obtained_at = item.get("obtainedAt", {}).get("S") or datetime.fromtimestamp(
        int(time.time()), timezone.utc
    ).isoformat()

    try:
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": SHOP_LISTINGS_TABLE,
                        "Key": {"listingId": {"S": listing_id}},
                        "ConditionExpression": (
                            "attribute_exists(listingId) AND sellerId = :seller"
                        ),
                        "ExpressionAttributeValues": {":seller": {"S": user_id}},
                    }
                },
                {
                    "Put": {
                        "TableName": USER_CARDS_TABLE,
                        "Item": {
                            "userId": {"S": user_id},
                            "ownedCardId": {"S": owned_card_id},
                            "obtainedAt": {"S": obtained_at},
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
                        "UpdateExpression": "ADD activeListings :minusOne",
                        "ExpressionAttributeValues": {":minusOne": {"N": "-1"}},
                    }
                },
            ]
        )
    except ClientError as error:
        if is_condition_failure(error):
            return not_found()
        return response(500, {"message": "Could not cancel the listing."})

    return response(
        200,
        {
            "listingId": listing_id,
            "card": {
                "ownedCardId": owned_card_id,
                "obtainedAt": obtained_at,
                "name": character["name"],
                "rarity": character["rarity"],
                "file_name": file_name,
            },
        },
    )
