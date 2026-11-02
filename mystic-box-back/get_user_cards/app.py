import json
import os
import unicodedata

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from mystic_shared.cards import get_character, sell_price

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")

# Criado uma vez por container e reaproveitado entre invocações.
_table = None


def get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(USER_CARDS_TABLE)
    return _table


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


SORT_FIELDS = ("obtainedAt", "rarity", "name")
SORT_ORDERS = ("asc", "desc")
DEFAULT_SORT = "obtainedAt"
DEFAULT_ORDER = "desc"


def name_key(card):
    # Ignora maiúsculas/minúsculas e acentos: "Ágata" == "agata".
    normalized = unicodedata.normalize("NFKD", card.get("name") or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold()


def rarity_key(card):
    return card.get("rarity") or 0


def obtained_at_key(card):
    return card.get("obtainedAt") or ""


# Campo -> (critério principal, critério de desempate sempre crescente).
SORT_KEYS = {
    "obtainedAt": (obtained_at_key, name_key),
    "rarity": (rarity_key, name_key),
    "name": (name_key, rarity_key),
}


def get_sort_params(event):
    params = event.get("queryStringParameters") or {}
    sort = params.get("sort") or DEFAULT_SORT
    order = params.get("order") or DEFAULT_ORDER

    if sort not in SORT_FIELDS:
        raise ValueError(f"Parâmetro 'sort' inválido. Use: {', '.join(SORT_FIELDS)}.")
    if order not in SORT_ORDERS:
        raise ValueError(f"Parâmetro 'order' inválido. Use: {', '.join(SORT_ORDERS)}.")

    return sort, order


def sort_cards(cards, sort, order):
    primary, secondary = SORT_KEYS[sort]
    # sort() é estável: ordena pelo desempate primeiro e depois pelo critério principal.
    ordered = sorted(cards, key=secondary)
    ordered.sort(key=primary, reverse=order == "desc")
    return ordered


def get_sell_price(file_name):
    character = get_character(file_name)
    return sell_price(character) if character else None


def get_user_id(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub")


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "Usuário não autenticado."})

    try:
        sort, order = get_sort_params(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    try:
        items = []
        query_kwargs = {
            "KeyConditionExpression": Key("userId").eq(user_id),
        }

        while True:
            result = get_table().query(**query_kwargs)
            items.extend(result.get("Items", []))

            last_key = result.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
    except ClientError:
        return response(500, {"message": "Não foi possível buscar suas cartas."})

    cards = [
        {
            "ownedCardId": item.get("ownedCardId"),
            "name": item.get("name"),
            "rarity": int(item["rarity"]) if item.get("rarity") is not None else None,
            "file_name": item.get("file_name"),
            "obtainedAt": item.get("obtainedAt"),
            # Preço definido no servidor; None = carta que não pode ser vendida.
            "sellPrice": get_sell_price(item.get("file_name")),
        }
        for item in items
    ]
    cards = sort_cards(cards, sort, order)

    return response(200, {"cards": cards})
