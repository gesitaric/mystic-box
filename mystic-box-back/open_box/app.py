"""POST /box/open: sorteia as cartas de uma invocação.

O sorteio consome o tempo de espera na hora e fica pendente no item do jogador
em `UserSummonStateTable` até ser guardado (`POST /users/me/cards`) ou expirar.
Abrir o portal com um sorteio pendente devolve esse mesmo sorteio: não dá para
sortear de novo e guardar só a melhor tirada.
"""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from mystic_shared import summon_token
from mystic_shared.cards import draw_cards, public_card
from mystic_shared.omens import FEATURED_SUMMON_MULTIPLIER, featured_file_names

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_SUMMON_STATE_TABLE = os.environ.get("USER_SUMMON_STATE_TABLE")
SUMMON_COOLDOWN_SECONDS = int(os.environ.get("SUMMON_COOLDOWN_SECONDS", "3600"))

# Criado uma vez por container e reaproveitado entre invocações.
_client = None


def get_client():
    global _client
    if _client is None:
        _client = boto3.client("dynamodb")
    return _client


def response(status_code, body, headers=None):
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, **(headers or {})},
        "body": json.dumps(body),
    }


def get_user_id(event):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub")


def get_state(user_id):
    result = get_client().get_item(
        TableName=USER_SUMMON_STATE_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    )
    return result.get("Item")


def last_summon_at(state):
    """Valor gravado de `lastSummonAt` (None se o jogador nunca invocou)."""
    value = (state or {}).get("lastSummonAt", {}).get("N")
    return int(value) if value is not None else None


def cooldown_response(retry_after):
    return response(
        429,
        {
            "message": "You are still on cooldown for summoning.",
            "retryAfterSeconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def store_pending(user_id, token, payload, previous):
    """Grava o sorteio pendente e consome o tempo de espera.

    Condição: `lastSummonAt` ainda é o lido (`previous`). Dois pedidos ao mesmo
    tempo não geram dois sorteios: o segundo falha e devolve o do primeiro.
    """
    if previous is None:
        condition = {"ConditionExpression": "attribute_not_exists(lastSummonAt)"}
        values = {}
    else:
        condition = {"ConditionExpression": "lastSummonAt = :previous"}
        values = {":previous": {"N": str(previous)}}

    get_client().update_item(
        TableName=USER_SUMMON_STATE_TABLE,
        Key={"userId": {"S": user_id}},
        UpdateExpression=(
            "SET lastSummonAt = :now, pendingToken = :token, "
            "pendingTokenId = :tokenId, pendingExpiresAt = :exp"
        ),
        ExpressionAttributeValues={
            ":now": {"N": str(payload["iat"])},
            ":token": {"S": token},
            ":tokenId": {"S": payload["id"]},
            ":exp": {"N": str(payload["exp"])},
            **values,
        },
        **condition,
    )


def is_conditional_failure(error):
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    now = int(time.time())
    try:
        state = get_state(user_id)
        pending = summon_token.pending_summon(state, user_id, now)
        if pending:
            return response(200, pending)

        previous = last_summon_at(state)
        retry_after = (
            0 if previous is None else previous + SUMMON_COOLDOWN_SECONDS - now
        )
        if retry_after > 0:
            return cooldown_response(retry_after)

        # Personagens da região do boato da semana têm mais chance.
        drawn = draw_cards(
            featured=featured_file_names(), multiplier=FEATURED_SUMMON_MULTIPLIER
        )
        # Só este token (e não as cartas) é aceito depois por POST /users/me/cards.
        token = summon_token.issue(
            (character["file_name"] for character in drawn), user_id, now=now
        )
        payload = summon_token.verify(token, now=now)

        try:
            store_pending(user_id, token, payload, previous)
        except ClientError as error:
            if not is_conditional_failure(error):
                raise
            # Outro pedido sorteou primeiro: devolve o sorteio dele.
            state = get_state(user_id)
            pending = summon_token.pending_summon(state, user_id, now)
            if pending:
                return response(200, pending)
            previous = last_summon_at(state) or now
            return cooldown_response(max(1, previous + SUMMON_COOLDOWN_SECONDS - now))
    except ClientError:
        return response(500, {"message": "Could not open the box."})

    return response(
        200,
        {
            "cards": [public_card(character) for character in drawn],
            "summonToken": token,
        },
    )
