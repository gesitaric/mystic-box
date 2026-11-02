import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.cards import get_character, sell_price

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

MAX_OWNED_CARD_ID_LENGTH = 64

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


def get_owned_card_id(event):
    owned_card_id = (event.get("pathParameters") or {}).get("ownedCardId")
    if (
        not isinstance(owned_card_id, str)
        or not owned_card_id
        or len(owned_card_id) > MAX_OWNED_CARD_ID_LENGTH
    ):
        return None
    return owned_card_id


def is_card_already_gone(error):
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return False

    reasons = error.response.get("CancellationReasons") or []
    return bool(reasons) and reasons[0].get("Code") == "ConditionalCheckFailed"


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

    owned_card_id = get_owned_card_id(event)
    if not owned_card_id:
        return response(400, {"message": "Carta inválida."})

    card_key = {"userId": {"S": user_id}, "ownedCardId": {"S": owned_card_id}}

    try:
        result = get_client().get_item(
            TableName=USER_CARDS_TABLE, Key=card_key, ConsistentRead=True
        )
    except ClientError:
        return response(500, {"message": "Não foi possível vender a carta."})

    item = result.get("Item")
    if not item:
        return response(404, {"message": "Carta não encontrada na sua coleção."})

    # O preço vem SEMPRE das definições do servidor.
    file_name = item.get("file_name", {}).get("S")
    character = get_character(file_name)
    if not character:
        return response(409, {"message": "Esta carta não pode ser vendida."})

    price = sell_price(character)

    try:
        # Remover a carta e creditar o valor é atômico. A condição no Delete
        # impede que a mesma carta seja vendida duas vezes.
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": USER_CARDS_TABLE,
                        "Key": card_key,
                        "ConditionExpression": (
                            "attribute_exists(ownedCardId) AND file_name = :fileName"
                        ),
                        "ExpressionAttributeValues": {":fileName": {"S": file_name}},
                    }
                },
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :price",
                        "ExpressionAttributeValues": {":price": {"N": str(price)}},
                    }
                },
            ]
        )
    except ClientError as error:
        if is_card_already_gone(error):
            return response(404, {"message": "Carta não encontrada na sua coleção."})
        return response(500, {"message": "Não foi possível vender a carta."})

    try:
        balance = get_balance(user_id)
    except ClientError:
        # A venda já aconteceu; o cliente consulta o saldo depois.
        balance = None

    return response(
        200,
        {"soldOwnedCardId": owned_card_id, "price": price, "balance": balance},
    )
