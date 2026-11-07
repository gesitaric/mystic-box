"""GET /battles/current: batalha ativa do jogador e opções para começar outra.

Devolve a batalha em andamento (ou null), as dificuldades (com as liberadas
pelo nível do jogador), o tamanho do time, o progresso do jogador e
`pvpBattleId`: o id do duelo online ativo (ou null), para o frontend abrir a
arena com uma chamada só quando não há duelo.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from mystic_shared.battle import TEAM_SIZE, public_difficulties, public_state
from mystic_shared.progression import level_for_experience, public_progress

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

BATTLES_TABLE = os.environ.get("BATTLES_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
PVP_PLAYERS_TABLE = os.environ.get("PVP_PLAYERS_TABLE")

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


def get_item(table, user_id):
    return get_client().get_item(
        TableName=table,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    try:
        battle_item = get_item(BATTLES_TABLE, user_id)
        progress_item = get_item(USER_PROGRESS_TABLE, user_id) or {}
        pvp_pointer = get_item(PVP_PLAYERS_TABLE, user_id) or {}
    except ClientError:
        return response(500, {"message": "Could not load the battle."})

    experience = int(progress_item.get("experience", {}).get("N", "0"))
    level, _ = level_for_experience(experience)

    battle = None
    if battle_item and battle_item.get("status", {}).get("S") == "active":
        battle = public_state(json.loads(battle_item["state"]["S"]))

    return response(
        200,
        {
            "battle": battle,
            "pvpBattleId": (
                pvp_pointer["battleId"]["S"]
                if pvp_pointer.get("status", {}).get("S") == "active"
                else None
            ),
            "teamSize": TEAM_SIZE,
            "difficulties": public_difficulties(level),
            "progress": public_progress(
                experience,
                wins=int(progress_item.get("wins", {}).get("N", "0")),
                losses=int(progress_item.get("losses", {}).get("N", "0")),
            ),
        },
    )
