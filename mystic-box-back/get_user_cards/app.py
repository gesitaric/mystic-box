import json
import os
import unicodedata

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from mystic_shared.ascension import public_ascension, read_ascensions
from mystic_shared.cards import get_character, listing_price_range, max_listing_quantity
from mystic_shared.battle import ascension_unlocks_skill, public_skills
from mystic_shared.lore import public_lore
from mystic_shared.stats import public_battle_profile

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
CARD_ASCENSIONS_TABLE = os.environ.get("CARD_ASCENSIONS_TABLE")

# Criados uma vez por container e reaproveitados entre invocações.
_table = None
_client = None


def get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(USER_CARDS_TABLE)
    return _table


def get_client():
    global _client
    if _client is None:
        _client = boto3.client("dynamodb")
    return _client


def get_ascensions(user_id):
    """{file_name: ascensão} do jogador."""
    return read_ascensions(get_client(), CARD_ASCENSIONS_TABLE, user_id)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


SORT_FIELDS = ("obtainedAt", "rarity", "name", "quantity")
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
    # Grupos de cartas repetidas são ordenados pela cópia mais recente.
    return card.get("lastObtainedAt") or ""


def quantity_key(card):
    return card.get("quantity") or 0


# Campo -> (critério principal, critério de desempate sempre crescente).
SORT_KEYS = {
    "obtainedAt": (obtained_at_key, name_key),
    "rarity": (rarity_key, name_key),
    "name": (name_key, rarity_key),
    "quantity": (quantity_key, lambda card: (name_key(card), rarity_key(card))),
}


def get_sort_params(event):
    params = event.get("queryStringParameters") or {}
    sort = params.get("sort") or DEFAULT_SORT
    order = params.get("order") or DEFAULT_ORDER

    if sort not in SORT_FIELDS:
        raise ValueError(f"Invalid 'sort' parameter. Use: {', '.join(SORT_FIELDS)}.")
    if order not in SORT_ORDERS:
        raise ValueError(f"Invalid 'order' parameter. Use: {', '.join(SORT_ORDERS)}.")

    return sort, order


def sort_cards(cards, sort, order):
    primary, secondary = SORT_KEYS[sort]
    # sort() é estável: ordena pelo desempate primeiro e depois pelo critério principal.
    ordered = sorted(cards, key=secondary)
    ordered.sort(key=primary, reverse=order == "desc")
    return ordered


def group_cards(items, ascensions=None):
    """Junta as cópias da mesma carta (mesmo `file_name`) em um só item.

    `ascensions`: {file_name: ascensão} do jogador; os atributos e as
    habilidades de batalha já saem com a ascensão aplicada.
    """
    ascensions = ascensions or {}
    groups = {}
    owned = {item.get("file_name") for item in items if item.get("file_name")}

    for item in items:
        file_name = item.get("file_name")
        # Cartas antigas sem `file_name` são agrupadas pelo nome.
        key = file_name or f"name:{item.get('name')}"
        group = groups.get(key)

        if group is None:
            groups[key] = group = {
                "file_name": file_name,
                "name": item.get("name"),
                "rarity": int(item["rarity"]) if item.get("rarity") is not None else None,
                "quantity": 0,
                "obtainedAt": [],
            }

        group["quantity"] += 1
        if item.get("obtainedAt"):
            group["obtainedAt"].append(item["obtainedAt"])

    cards = []
    for group in groups.values():
        character = get_character(group["file_name"])
        if character:
            # Nome e raridade oficiais vêm das definições do servidor.
            group["name"] = character["name"]
            group["rarity"] = character["rarity"]
        obtained_at = group.pop("obtainedAt")
        ascension = ascensions.get(group["file_name"], 0)
        cards.append(
            {
                **group,
                "firstObtainedAt": min(obtained_at, default=None),
                "lastObtainedAt": max(obtained_at, default=None),
                # Faixa de preço (por cópia) aceita ao anunciar no mercado;
                # None = não pode ser anunciada.
                "listingPriceRange": listing_price_range(character),
                # Quantas cópias podem ser anunciadas de uma vez.
                "maxListingQuantity": max_listing_quantity(character, group["quantity"]),
                "battle": battle_profile(character, ascension) if character else None,
                # História, região, laços (com quem o jogador já tem) e o
                # capítulo secreto (liberado pela ascensão), ou None.
                "lore": public_lore(character, ascension, owned),
                # Ascensão (cópias repetidas fortalecem a carta); None = não ascende.
                "ascension": (
                    public_ascension(
                        ascension, group["quantity"], ascension_unlocks_skill(character)
                    )
                    if character
                    else None
                ),
            }
        )

    return cards


def battle_profile(character, ascension=0):
    """Elemento, arquétipo, atributos (nível 1) e habilidades de batalha da carta."""
    return {
        **public_battle_profile(character, ascension=ascension),
        "skills": public_skills(character, ascension),
    }


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
        return response(401, {"message": "User is not authenticated."})

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
        ascensions = get_ascensions(user_id)
    except ClientError:
        return response(500, {"message": "Could not load your cards."})

    cards = sort_cards(group_cards(items, ascensions), sort, order)

    return response(200, {"cards": cards, "totalCards": len(items)})
