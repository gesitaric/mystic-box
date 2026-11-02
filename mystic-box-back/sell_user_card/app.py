import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import (
    MAX_SELL_QUANTITY,
    get_character,
    sell_price,
    sell_total,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

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
    """(file_name, quantity) pedidos pelo cliente. Lança ValueError se inválidos.

    O cliente só diz QUAL carta e QUANTAS cópias quer vender; preço e quais
    cópias saem da coleção são decididos aqui.
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
        or not 1 <= quantity <= MAX_SELL_QUANTITY
    ):
        raise ValueError(
            f"Invalid quantity. Choose from 1 to {MAX_SELL_QUANTITY} copies."
        )

    return file_name, quantity


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


def is_collection_changed(error):
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return False

    reasons = error.response.get("CancellationReasons") or []
    return any(reason.get("Code") == "ConditionalCheckFailed" for reason in reasons)


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

    try:
        file_name, quantity = parse_request(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    try:
        copies = get_owned_copies(user_id, file_name)
    except ClientError:
        return response(500, {"message": "Could not sell the card."})

    if not copies:
        return response(404, {"message": "Card not found in your collection."})

    # O preço vem SEMPRE das definições do servidor.
    character = get_character(file_name)
    if not character:
        return response(409, {"message": "This card cannot be sold."})

    if quantity > len(copies):
        return response(
            409,
            {
                "message": f"You only have {len(copies)} copy(ies) of this card.",
                "available": len(copies),
            },
        )

    # Vende as cópias mais recentes e mantém as mais antigas na coleção.
    sold_ids = [copy["ownedCardId"] for copy in copies[:quantity]]
    total = sell_total(character, quantity)

    try:
        # Remover as cartas e creditar o valor é atômico. A condição em cada
        # Delete impede que a mesma carta seja vendida duas vezes.
        get_client().transact_write_items(
            TransactItems=[
                *(
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
                            "ExpressionAttributeValues": {
                                ":fileName": {"S": file_name}
                            },
                        }
                    }
                    for owned_card_id in sold_ids
                ),
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :price",
                        "ExpressionAttributeValues": {":price": {"N": str(total)}},
                    }
                },
            ]
        )
    except ClientError as error:
        if is_collection_changed(error):
            return response(
                409,
                {
                    "message": (
                        "Your collection changed during the sale. Nothing was sold; "
                        "please try again."
                    )
                },
            )
        return response(500, {"message": "Could not sell the card."})

    try:
        balance = get_balance(user_id)
    except ClientError:
        # A venda já aconteceu; o cliente consulta o saldo depois.
        balance = None

    return response(
        200,
        {
            "fileName": file_name,
            "name": character["name"],
            "soldQuantity": quantity,
            "soldOwnedCardIds": sold_ids,
            "remainingQuantity": len(copies) - quantity,
            "unitPrice": sell_price(character),
            "price": total,
            "balance": balance,
        },
    )
