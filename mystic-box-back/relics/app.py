"""Relíquias do jogador: ver, forjar e equipar.

Rotas:
- GET /users/me/relics?fileName=: todas as relíquias, quantas o jogador tem,
  em quem estão equipadas e se pode forjar mais. Com `fileName`, cada uma traz
  em `forCard` o efeito nessa personagem e `equipped` diz qual ela usa.
- POST /users/me/relics/forge: {"relicId"} forja uma cópia (só de regiões
  cujo chefe o jogador já venceu). Numa só transação: debita os Fragmentos
  (condição: saldo cobre), soma a cópia (condição: abaixo do máximo) e confere
  o progresso da campanha.
- POST /users/me/relics/equip: {"fileName", "relicId" | null} equipa, troca ou
  tira a relíquia de uma personagem. Numa só transação: grava o equipamento da
  personagem (condição: ainda é o lido), ocupa uma cópia livre da relíquia
  nova (condição: `equipped < owned`) e libera a antiga.

O cliente só manda identificadores. Custos, limites e efeitos vêm de
`mystic_shared.relics`.
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.campaign import STAGES_PER_REGION, progress_from_item, stage_attribute
from mystic_shared.cards import get_character
from mystic_shared.relics import (
    FORGE_COST,
    MAX_COPIES,
    get_relic,
    grant_update,
    public_equipped,
    public_inventory,
    read_equipped,
    read_owned,
)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_RELICS_TABLE = os.environ.get("USER_RELICS_TABLE")
CARD_RELICS_TABLE = os.environ.get("CARD_RELICS_TABLE")
REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

LIST_ROUTE = "/users/me/relics"
FORGE_ROUTE = "/users/me/relics/forge"
EQUIP_ROUTE = "/users/me/relics/equip"

MAX_ID_LENGTH = 64

# Posições dos itens na transação de forja.
FORGE_WALLET_ITEM, FORGE_RELIC_ITEM, FORGE_PROGRESS_ITEM = 0, 1, 2

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


def parse_body(event):
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, ValueError):
        body = None
    if not isinstance(body, dict):
        raise ValueError("Invalid request body.")
    return body


def is_short_string(value):
    return isinstance(value, str) and 0 < len(value) <= MAX_ID_LENGTH


def failed_items(error):
    """Índices dos itens da transação cuja condição falhou (None se não foi isso)."""
    if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
        return None
    reasons = error.response.get("CancellationReasons") or []
    return {
        index
        for index, reason in enumerate(reasons)
        if reason.get("Code") == "ConditionalCheckFailed"
    }


# ------------------------------------------------------------------ leitura ---


def get_balance(user_id):
    item = get_client().get_item(
        TableName=USER_WALLET_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item") or {}
    return int(float(item.get("balance", {}).get("N", "0")))


def get_unlocked_regions(user_id):
    """Regiões cujo chefe o jogador já venceu."""
    item = get_client().get_item(
        TableName=REGION_PROGRESS_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")
    return {
        region for region, cleared in progress_from_item(item).items()
        if cleared >= STAGES_PER_REGION
    }


def owns_card(user_id, file_name):
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "FilterExpression": "file_name = :fileName",
        "ProjectionExpression": "file_name",
        "ExpressionAttributeValues": {
            ":userId": {"S": user_id},
            ":fileName": {"S": file_name},
        },
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        if result.get("Items"):
            return True
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return False
        query_kwargs["ExclusiveStartKey"] = last_key


def inventory(user_id, file_name=None):
    owned = read_owned(get_client(), USER_RELICS_TABLE, user_id)
    equipped = read_equipped(get_client(), CARD_RELICS_TABLE, user_id)
    balance = get_balance(user_id)
    return {
        "relics": public_inventory(
            owned, equipped, get_unlocked_regions(user_id), balance, file_name
        ),
        "balance": balance,
        "forgeCost": FORGE_COST,
        "maxCopies": MAX_COPIES,
        "equipped": equipped.get(file_name) if file_name else None,
    }


def card_param(value):
    """`fileName` opcional de uma carta conhecida (senão None)."""
    return value if is_short_string(value) and get_character(value) else None


# ------------------------------------------------------------------- rotas ---


def list_relics(user_id, event):
    params = event.get("queryStringParameters") or {}
    try:
        return response(200, inventory(user_id, card_param(params.get("fileName"))))
    except ClientError:
        return response(500, {"message": "Could not load your relics."})


def forge(user_id, event):
    try:
        body = parse_body(event)
    except ValueError as error:
        return response(400, {"message": str(error)})
    relic_id = body.get("relicId")
    relic = get_relic(relic_id) if is_short_string(relic_id) else None
    if not relic:
        return response(404, {"message": "Unknown relic."})

    grant = grant_update(USER_RELICS_TABLE, user_id, relic_id)["Update"]
    try:
        get_client().transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :charge",
                        "ConditionExpression": "balance >= :cost",
                        "ExpressionAttributeValues": {
                            ":charge": {"N": str(-FORGE_COST)},
                            ":cost": {"N": str(FORGE_COST)},
                        },
                    }
                },
                {
                    "Update": {
                        **grant,
                        "ConditionExpression": "attribute_not_exists(owned) OR owned < :max",
                        "ExpressionAttributeValues": {
                            **grant["ExpressionAttributeValues"],
                            ":max": {"N": str(MAX_COPIES)},
                        },
                    }
                },
                # Só forja quem já venceu o chefe da região.
                {
                    "ConditionCheck": {
                        "TableName": REGION_PROGRESS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "ConditionExpression": "#stage >= :stages",
                        "ExpressionAttributeNames": {
                            "#stage": stage_attribute(relic["region"])
                        },
                        "ExpressionAttributeValues": {
                            ":stages": {"N": str(STAGES_PER_REGION)}
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        failed = failed_items(error)
        if not failed:
            return response(500, {"message": "Could not forge the relic."})
        if FORGE_PROGRESS_ITEM in failed:
            return response(
                409, {"message": "Defeat this land's boss in the campaign first."}
            )
        if FORGE_RELIC_ITEM in failed:
            return response(
                409, {"message": f"You already have {MAX_COPIES} copies of {relic['name']}."}
            )
        return response(409, {"message": "Not enough Arcane Shards to forge this relic."})

    try:
        payload = inventory(user_id, card_param(body.get("fileName")))
        return response(200, {**payload, "forged": relic_id})
    except ClientError:
        return response(200, {"forged": relic_id})


def equip_items(user_id, key, relic_id, current):
    """Itens da transação de equipar/trocar/tirar. O primeiro é o da personagem."""
    if current:
        card_condition = {
            "ConditionExpression": "relicId = :current",
            "ExpressionAttributeValues": {":current": {"S": current}},
        }
    else:
        card_condition = {"ConditionExpression": "attribute_not_exists(relicId)"}

    items = []
    if relic_id:
        equipped_at = datetime.fromtimestamp(int(time.time()), timezone.utc).isoformat()
        items.append(
            {
                "Put": {
                    "TableName": CARD_RELICS_TABLE,
                    "Item": {
                        **key,
                        "relicId": {"S": relic_id},
                        "equippedAt": {"S": equipped_at},
                    },
                    **card_condition,
                }
            }
        )
        # Ocupa uma cópia livre da relíquia nova.
        items.append(
            {
                "Update": {
                    "TableName": USER_RELICS_TABLE,
                    "Key": {"userId": {"S": user_id}, "relicId": {"S": relic_id}},
                    "UpdateExpression": "ADD equipped :one",
                    "ConditionExpression": "equipped < owned",
                    "ExpressionAttributeValues": {":one": {"N": "1"}},
                }
            }
        )
    else:
        items.append(
            {"Delete": {"TableName": CARD_RELICS_TABLE, "Key": key, **card_condition}}
        )
    if current:
        # Libera a cópia da relíquia que estava equipada.
        items.append(
            {
                "Update": {
                    "TableName": USER_RELICS_TABLE,
                    "Key": {"userId": {"S": user_id}, "relicId": {"S": current}},
                    "UpdateExpression": "ADD equipped :minus",
                    "ConditionExpression": "equipped > :zero",
                    "ExpressionAttributeValues": {
                        ":minus": {"N": "-1"},
                        ":zero": {"N": "0"},
                    },
                }
            }
        )
    return items


def equip(user_id, event):
    try:
        body = parse_body(event)
    except ValueError as error:
        return response(400, {"message": str(error)})
    file_name = body.get("fileName")
    relic_id = body.get("relicId")
    character = get_character(file_name) if is_short_string(file_name) else None
    if not character:
        return response(400, {"message": "Unknown card."})
    relic = None
    if relic_id is not None:
        relic = get_relic(relic_id) if is_short_string(relic_id) else None
        if not relic:
            return response(404, {"message": "Unknown relic."})

    key = {"userId": {"S": user_id}, "file_name": {"S": file_name}}
    try:
        if not owns_card(user_id, file_name):
            return response(
                409, {"message": f"{character['name']} is not in your collection."}
            )
        current_item = get_client().get_item(
            TableName=CARD_RELICS_TABLE, Key=key, ConsistentRead=True
        ).get("Item") or {}
    except ClientError:
        return response(500, {"message": "Could not equip the relic."})
    current = current_item.get("relicId", {}).get("S")

    if current != relic_id:
        try:
            get_client().transact_write_items(
                TransactItems=equip_items(user_id, key, relic_id, current)
            )
        except ClientError as error:
            failed = failed_items(error)
            if not failed:
                return response(500, {"message": "Could not equip the relic."})
            if relic_id and 0 not in failed and 1 in failed:
                return response(
                    409,
                    {"message": f"No free copy of {relic['name']}. Forge another or "
                                "take it off another champion."},
                )
            return response(
                409, {"message": "Your relics changed in another window. Reload them."}
            )

    try:
        payload = inventory(user_id, file_name)
    except ClientError:
        payload = {}
    return response(
        200,
        {
            **payload,
            "card": {"fileName": file_name, "relic": public_equipped(relic_id, file_name)},
        },
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    resource = event.get("resource")
    method = event.get("httpMethod")
    if resource == LIST_ROUTE and method == "GET":
        return list_relics(user_id, event)
    if resource == FORGE_ROUTE and method == "POST":
        return forge(user_id, event)
    if resource == EQUIP_ROUTE and method == "POST":
        return equip(user_id, event)
    return response(404, {"message": "Not found."})
