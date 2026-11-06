"""Desafios do duelo online.

Rotas:
- GET /pvp: desafios recebidos e enviados, duelo ativo e regras do online.
- POST /pvp/challenges: {"username", "team": [fileName x3]} desafia um jogador.
- POST /pvp/challenges/accept: {"challengeId", "team"} aceita e começa o duelo.
- POST /pvp/challenges/decline: {"challengeId"} recusa um desafio recebido.
- POST /pvp/challenges/cancel: {"challengeId"} cancela um desafio enviado.

Quem desafia precisa ter nome de usuário; o adversário é encontrado pelo nome
(UsernamesTable). A posse das cartas dos dois times é conferida no servidor,
e o duelo começa numa só transação que apaga o desafio, cria a batalha e marca
os dois jogadores como em duelo (um duelo ativo por jogador). O id do Cognito
dos outros jogadores não é exposto.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared import pvp
from mystic_shared.battle import TEAM_SIZE, BattleError, create_pvp_battle, new_rng
from mystic_shared.cards import get_character
from mystic_shared.progression import level_for_experience
from mystic_shared.usernames import normalize, validate_username

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

PVP_CHALLENGES_TABLE = os.environ.get("PVP_CHALLENGES_TABLE")
PVP_BATTLES_TABLE = os.environ.get("PVP_BATTLES_TABLE")
PVP_PLAYERS_TABLE = os.environ.get("PVP_PLAYERS_TABLE")
USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")
USERNAMES_TABLE = os.environ.get("USERNAMES_TABLE")
USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
CHALLENGER_INDEX = "ChallengerIndex"

# Duelos somem sozinhos (TTL) um dia depois da última ação.
BATTLE_TTL_SECONDS = 24 * 60 * 60

MAX_ID_LENGTH = 64

LOBBY_ROUTE = "/pvp"
CHALLENGE_ROUTE = "/pvp/challenges"
ACCEPT_ROUTE = "/pvp/challenges/accept"
DECLINE_ROUTE = "/pvp/challenges/decline"
CANCEL_ROUTE = "/pvp/challenges/cancel"

# Posições na transação que começa o duelo.
CHALLENGE_ITEM = 0
CHALLENGER_POINTER_ITEM = 2
OPPONENT_POINTER_ITEM = 3

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
        raise ValueError("Invalid request body.")
    if not isinstance(body, dict):
        raise ValueError("Invalid request body.")
    return body


def is_short_string(value):
    return isinstance(value, str) and 0 < len(value) <= MAX_ID_LENGTH


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


def is_conditional_failure(error):
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


class RequestError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# ------------------------------------------------------------------ leitura ---


def get_item(table, key):
    return get_client().get_item(TableName=table, Key=key, ConsistentRead=True).get("Item")


def get_username(user_id):
    item = get_item(USER_PROFILES_TABLE, {"userId": {"S": user_id}}) or {}
    return item.get("username", {}).get("S")


def find_user_id(username):
    """Dono do nome (sem diferenciar maiúsculas) ou None."""
    item = get_item(USERNAMES_TABLE, {"usernameLower": {"S": normalize(username)}})
    return item["userId"]["S"] if item else None


def get_owned_file_names(user_id):
    names = set()
    query_kwargs = {
        "TableName": USER_CARDS_TABLE,
        "KeyConditionExpression": "userId = :userId",
        "ProjectionExpression": "file_name",
        "ExpressionAttributeValues": {":userId": {"S": user_id}},
        "ConsistentRead": True,
    }
    while True:
        result = get_client().query(**query_kwargs)
        names.update(
            item["file_name"]["S"] for item in result.get("Items", []) if "file_name" in item
        )
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return names
        query_kwargs["ExclusiveStartKey"] = last_key


def get_level(user_id):
    item = get_item(USER_PROGRESS_TABLE, {"userId": {"S": user_id}}) or {}
    return level_for_experience(int(item.get("experience", {}).get("N", "0")))[0]


def get_levels(user_ids):
    user_ids = list(dict.fromkeys(user_ids))
    if not user_ids:
        return {}
    result = get_client().batch_get_item(
        RequestItems={
            USER_PROGRESS_TABLE: {
                "Keys": [{"userId": {"S": user_id}} for user_id in user_ids],
                "ProjectionExpression": "userId, experience",
            }
        }
    )
    experience = {
        item["userId"]["S"]: int(item.get("experience", {}).get("N", "0"))
        for item in result.get("Responses", {}).get(USER_PROGRESS_TABLE, [])
    }
    return {
        user_id: level_for_experience(experience.get(user_id, 0))[0] for user_id in user_ids
    }


def query_all(**kwargs):
    items = []
    while True:
        result = get_client().query(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def incoming_challenges(user_id):
    return query_all(
        TableName=PVP_CHALLENGES_TABLE,
        KeyConditionExpression="opponentId = :me",
        ExpressionAttributeValues={":me": {"S": user_id}},
        ConsistentRead=True,
    )


def outgoing_challenges(user_id):
    return query_all(
        TableName=PVP_CHALLENGES_TABLE,
        IndexName=CHALLENGER_INDEX,
        KeyConditionExpression="challengerId = :me",
        ExpressionAttributeValues={":me": {"S": user_id}},
    )


def active_challenges(items, now):
    return [item for item in items if pvp.challenge_active(item["expiresAt"]["N"], now)]


def active_duel(user_id):
    """Ponteiro do duelo ativo do jogador, ou None.

    Um ponteiro "active" cujo duelo já sumiu (TTL) é apagado aqui.
    """
    pointer = get_item(PVP_PLAYERS_TABLE, {"userId": {"S": user_id}})
    if not pointer or pointer.get("status", {}).get("S") != "active":
        return None
    battle_id = pointer["battleId"]["S"]
    if get_item(PVP_BATTLES_TABLE, {"battleId": {"S": battle_id}}):
        return pointer
    try:
        get_client().delete_item(
            TableName=PVP_PLAYERS_TABLE,
            Key={"userId": {"S": user_id}},
            ConditionExpression="battleId = :battleId",
            ExpressionAttributeValues={":battleId": {"S": battle_id}},
        )
    except ClientError as error:
        if not is_conditional_failure(error):
            raise
        return get_item(PVP_PLAYERS_TABLE, {"userId": {"S": user_id}})
    return None


# ------------------------------------------------------------------ regras ---


def parse_team(team):
    """Cartas do servidor para os nomes de arquivo enviados (só identificadores)."""
    if (
        not isinstance(team, list)
        or len(team) != TEAM_SIZE
        or not all(is_short_string(name) for name in team)
    ):
        raise RequestError(400, f"Choose exactly {TEAM_SIZE} cards.")
    if len(set(team)) != TEAM_SIZE:
        raise RequestError(400, "Choose different cards.")
    characters = [get_character(name) for name in team]
    if any(character is None for character in characters):
        raise RequestError(400, "Unknown card.")
    return characters


def missing_cards(user_id, characters):
    owned = get_owned_file_names(user_id)
    return [c["name"] for c in characters if c["file_name"] not in owned]


def require_owned(user_id, characters):
    missing = missing_cards(user_id, characters)
    if missing:
        raise RequestError(409, f"{', '.join(missing)} is not in your collection.")


def public_challenge(item, username_field, user_id_field, levels, now):
    return {
        "challengeId": item["challengeId"]["S"],
        "username": item[username_field]["S"],
        "level": levels.get(item[user_id_field]["S"], 1),
        "expiresInSeconds": max(0, int(item["expiresAt"]["N"]) - int(now)),
    }


# ------------------------------------------------------------------- rotas ---


def lobby(user_id):
    now = int(time.time())
    username = get_username(user_id)
    incoming = active_challenges(incoming_challenges(user_id), now)
    outgoing = active_challenges(outgoing_challenges(user_id), now)
    levels = get_levels(
        [item["challengerId"]["S"] for item in incoming]
        + [item["opponentId"]["S"] for item in outgoing]
    )
    incoming.sort(key=lambda item: int(item["createdAt"]["N"]), reverse=True)
    outgoing.sort(key=lambda item: int(item["createdAt"]["N"]), reverse=True)

    duel = None
    pointer = active_duel(user_id)
    if pointer:
        duel = {
            "battleId": pointer["battleId"]["S"],
            "opponent": pointer.get("opponentName", {}).get("S"),
        }

    return response(
        200,
        {
            "username": username,
            "hasUsername": bool(username),
            "incoming": [
                public_challenge(item, "challengerName", "challengerId", levels, now)
                for item in incoming
            ],
            "outgoing": [
                public_challenge(item, "opponentName", "opponentId", levels, now)
                for item in outgoing
            ],
            "battle": duel,
            "rules": pvp.public_rules(),
        },
    )


def challenge(user_id, body):
    my_name = get_username(user_id)
    if not my_name:
        raise RequestError(409, "Choose a username before challenging other players.")

    characters = parse_team(body.get("team"))
    target, error = validate_username(body.get("username"))
    if error:
        raise RequestError(404, "Player not found.")

    opponent_id = find_user_id(target)
    if not opponent_id:
        raise RequestError(404, "Player not found.")
    if opponent_id == user_id:
        raise RequestError(400, "You cannot challenge yourself.")
    opponent_name = get_username(opponent_id) or target

    require_owned(user_id, characters)
    if active_duel(user_id):
        raise RequestError(409, "Finish your current duel first.")

    now = int(time.time())
    if len(active_challenges(outgoing_challenges(user_id), now)) >= pvp.MAX_OUTGOING_CHALLENGES:
        raise RequestError(
            429,
            f"You can have at most {pvp.MAX_OUTGOING_CHALLENGES} open challenges. "
            "Wait for an answer or cancel one.",
        )

    challenge_id = str(uuid.uuid4())
    expires_at = now + pvp.CHALLENGE_TTL_SECONDS
    try:
        # Um desafio por par: só substitui um desafio anterior já expirado.
        get_client().put_item(
            TableName=PVP_CHALLENGES_TABLE,
            Item={
                "opponentId": {"S": opponent_id},
                "challengerId": {"S": user_id},
                "challengeId": {"S": challenge_id},
                "challengerName": {"S": my_name},
                "opponentName": {"S": opponent_name},
                "team": {"S": json.dumps([c["file_name"] for c in characters])},
                "createdAt": {"N": str(now)},
                "expiresAt": {"N": str(expires_at)},
            },
            ConditionExpression="attribute_not_exists(challengerId) OR expiresAt <= :now",
            ExpressionAttributeValues={":now": {"N": str(now)}},
        )
    except ClientError as error:
        if is_conditional_failure(error):
            raise RequestError(409, f"You already challenged {opponent_name}.") from error
        raise

    return response(
        201,
        {
            "challenge": {
                "challengeId": challenge_id,
                "username": opponent_name,
                "level": get_level(opponent_id),
                "expiresInSeconds": pvp.CHALLENGE_TTL_SECONDS,
            }
        },
    )


def find_incoming(user_id, challenge_id, now):
    for item in active_challenges(incoming_challenges(user_id), now):
        if item["challengeId"]["S"] == challenge_id:
            return item
    raise RequestError(404, "This challenge is no longer available.")


def delete_challenge(item):
    try:
        get_client().delete_item(
            TableName=PVP_CHALLENGES_TABLE,
            Key={"opponentId": item["opponentId"], "challengerId": item["challengerId"]},
            ConditionExpression="challengeId = :id",
            ExpressionAttributeValues={":id": item["challengeId"]},
        )
    except ClientError as error:
        if is_conditional_failure(error):
            raise RequestError(404, "This challenge is no longer available.") from error
        raise


def pointer_put(user_id, battle_id, side, opponent_name):
    return {
        "TableName": PVP_PLAYERS_TABLE,
        "Item": {
            "userId": {"S": user_id},
            "battleId": {"S": battle_id},
            "side": {"S": side},
            "status": {"S": "active"},
            "opponentName": {"S": opponent_name},
        },
        # Um duelo ativo por jogador.
        "ConditionExpression": "attribute_not_exists(userId) OR #status <> :active",
        "ExpressionAttributeNames": {"#status": "status"},
        "ExpressionAttributeValues": {":active": {"S": "active"}},
    }


def accept(user_id, body):
    challenge_id = body.get("challengeId")
    if not is_short_string(challenge_id):
        raise RequestError(400, "Invalid challenge.")
    characters = parse_team(body.get("team"))

    now = int(time.time())
    item = find_incoming(user_id, challenge_id, now)
    challenger_id = item["challengerId"]["S"]
    challenger_name = item["challengerName"]["S"]
    my_name = get_username(user_id) or item["opponentName"]["S"]

    require_owned(user_id, characters)

    challenger_team = [get_character(name) for name in json.loads(item["team"]["S"])]
    if any(c is None for c in challenger_team) or missing_cards(challenger_id, challenger_team):
        delete_challenge(item)
        raise RequestError(
            409,
            f"{challenger_name} no longer has the cards of this challenge. "
            "The challenge was cancelled.",
        )

    if active_duel(user_id):
        raise RequestError(409, "Finish your current duel first.")
    if active_duel(challenger_id):
        raise RequestError(409, f"{challenger_name} is already in another duel.")

    battle_id = str(uuid.uuid4())
    try:
        state, events = create_pvp_battle(
            battle_id,
            challenger_team,
            get_level(challenger_id),
            characters,
            get_level(user_id),
            new_rng(),
        )
    except BattleError as error:
        raise RequestError(400, str(error)) from error
    pvp.start_online(state, events, now)

    players = {
        "player": {"userId": challenger_id, "username": challenger_name},
        "enemy": {"userId": user_id, "username": my_name},
    }
    transact_items = [
        {
            "Delete": {
                "TableName": PVP_CHALLENGES_TABLE,
                "Key": {"opponentId": item["opponentId"], "challengerId": item["challengerId"]},
                "ConditionExpression": "challengeId = :id",
                "ExpressionAttributeValues": {":id": item["challengeId"]},
            }
        },
        {
            "Put": {
                "TableName": PVP_BATTLES_TABLE,
                "Item": {
                    "battleId": {"S": battle_id},
                    "status": {"S": state["status"]},
                    "version": {"N": "1"},
                    "state": {"S": json.dumps(state)},
                    "players": {"S": json.dumps(players)},
                    "updatedAt": {"S": datetime.fromtimestamp(now, timezone.utc).isoformat()},
                    "expiresAt": {"N": str(now + BATTLE_TTL_SECONDS)},
                },
                "ConditionExpression": "attribute_not_exists(battleId)",
            }
        },
        {"Put": pointer_put(challenger_id, battle_id, "player", my_name)},
        {"Put": pointer_put(user_id, battle_id, "enemy", challenger_name)},
    ]
    try:
        get_client().transact_write_items(TransactItems=transact_items)
    except ClientError as error:
        failed = get_failed_conditions(error)
        if CHALLENGE_ITEM in failed:
            raise RequestError(404, "This challenge is no longer available.") from error
        if OPPONENT_POINTER_ITEM in failed:
            raise RequestError(409, "Finish your current duel first.") from error
        if CHALLENGER_POINTER_ITEM in failed:
            raise RequestError(409, f"{challenger_name} is already in another duel.") from error
        raise

    return response(201, {"battleId": battle_id})


def decline(user_id, body):
    challenge_id = body.get("challengeId")
    if not is_short_string(challenge_id):
        raise RequestError(400, "Invalid challenge.")
    delete_challenge(find_incoming(user_id, challenge_id, int(time.time())))
    return response(200, {"challengeId": challenge_id})


def cancel(user_id, body):
    challenge_id = body.get("challengeId")
    if not is_short_string(challenge_id):
        raise RequestError(400, "Invalid challenge.")
    for item in outgoing_challenges(user_id):
        if item["challengeId"]["S"] == challenge_id:
            delete_challenge(item)
            return response(200, {"challengeId": challenge_id})
    raise RequestError(404, "This challenge is no longer available.")


ROUTES = {
    ("POST", CHALLENGE_ROUTE): challenge,
    ("POST", ACCEPT_ROUTE): accept,
    ("POST", DECLINE_ROUTE): decline,
    ("POST", CANCEL_ROUTE): cancel,
}


def lambda_handler(event, context):
    method = event.get("httpMethod")
    if method == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    resource = event.get("resource")
    try:
        if method == "GET" and resource == LOBBY_ROUTE:
            return lobby(user_id)
        handler = ROUTES.get((method, resource))
        if handler is None:
            return response(404, {"message": "Not found."})
        try:
            body = parse_body(event)
        except ValueError as error:
            return response(400, {"message": str(error)})
        return handler(user_id, body)
    except RequestError as error:
        return response(error.status_code, {"message": error.message})
    except ClientError:
        return response(500, {"message": "Could not reach the arena. Try again."})
