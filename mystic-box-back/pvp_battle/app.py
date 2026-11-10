"""Duelo online em andamento.

Rotas:
- GET /pvp/battle?since=N&battleId=X: duelo do jogador (ativo ou o último
  que acabou), visto do lado dele, com os eventos depois do lote N para
  animar. Com `battleId` lê só o duelo (confere se o jogador é um dos dois);
  sem ele, acha o duelo pelo ponteiro do jogador. Se nada mudou desde o lote
  N, devolve só `unchanged` com o tempo de turno.
- POST /pvp/battle/actions: {"battleId", "type": "skill"|"auto"|"forfeit",
  "skill"?, "target"?, "since"?} joga a vez da carta do jogador.
- GET /pvp/watch?battleId=X&since=N: o duelo visto por quem assiste (qualquer
  jogador com sessão que não seja um dos dois), com os eventos depois do lote
  N. Só lê: vezes vencidas ficam para a próxima requisição dos jogadores.

As regras da batalha são as de mystic_shared.battle; o tempo de turno e o
abandono, de mystic_shared.pvp. Vezes com o tempo esgotado são jogadas no
automático na próxima requisição de qualquer um dos dois jogadores. O estado
fica em PvpBattlesTable com versão (condição em cada gravação). No fim,
resultado, experiência e Fragmentos Arcanos de subida de nível dos dois
jogadores são gravados numa só transação.
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared import pvp
from mystic_shared.battle import (
    SPECTATOR,
    BattleError,
    battle_experience,
    new_rng,
    outcome_for,
    view_id,
    view_reason,
)
from mystic_shared.progression import level_for_experience, level_up_reward, public_progress

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

PVP_BATTLES_TABLE = os.environ.get("PVP_BATTLES_TABLE")
PVP_PLAYERS_TABLE = os.environ.get("PVP_PLAYERS_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")

# Duelos somem sozinhos (TTL) um dia depois da última ação; o ponteiro de um
# duelo que acabou, uma semana depois.
BATTLE_TTL_SECONDS = 24 * 60 * 60
FINISHED_POINTER_TTL_SECONDS = 7 * 24 * 60 * 60

MAX_ID_LENGTH = 64
ACTION_TYPES = ("skill", "auto", "forfeit")
SIDES = ("player", "enemy")

# Posições na transação de fim de duelo: batalha, progresso de cada lado.
BATTLE_ITEM = 0
PROGRESS_ITEMS = {1, 2}
FINISH_ATTEMPTS = 3

BATTLE_ROUTE = "/pvp/battle"
ACTION_ROUTE = "/pvp/battle/actions"
WATCH_ROUTE = "/pvp/watch"

# Criado uma vez por container e reaproveitado entre invocações.
_client = None


class BattleChanged(Exception):
    """O duelo foi alterado por outra requisição ao mesmo tempo."""


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


def parse_since(value):
    """Último lote de eventos que o cliente já viu (None = só o estado)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        since = int(value)
    except (TypeError, ValueError):
        return None
    return since if since >= 0 else None


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


# ------------------------------------------------------------------ leitura ---


def get_item(table, key):
    return get_client().get_item(TableName=table, Key=key, ConsistentRead=True).get("Item")


class Duel:
    """Duelo carregado do banco, do ponto de vista de quem pediu."""

    def __init__(self, side, item):
        self.side = side
        self.battle_id = item["battleId"]["S"]
        self.state = json.loads(item["state"]["S"])
        self.version = int(item["version"]["N"])
        self.players = json.loads(item["players"]["S"])
        # Duelos de antes da lista de duelos em andamento não têm startedAt.
        self.started_at = int(item.get("startedAt", {}).get("N", "0")) or int(time.time())

    def public_players(self):
        return {
            side: {
                "username": self.players[side]["username"],
                "level": self.state[f"{side}Level"],
                "title": self.players[side].get("title"),
            }
            for side in SIDES
        }

    def has_player(self, user_id):
        return any(self.players[side]["userId"] == user_id for side in SIDES)


def load_duel(user_id, battle_id=None):
    """Duelo do jogador. Com `battle_id`, uma leitura só (sem o ponteiro)."""
    if battle_id is not None:
        item = get_item(PVP_BATTLES_TABLE, {"battleId": {"S": battle_id}})
        if not item:
            return None
        players = json.loads(item["players"]["S"])
        side = next((s for s in SIDES if players[s]["userId"] == user_id), None)
        return Duel(side, item) if side else None

    pointer = get_item(PVP_PLAYERS_TABLE, {"userId": {"S": user_id}})
    if not pointer:
        return None
    item = get_item(PVP_BATTLES_TABLE, {"battleId": pointer["battleId"]})
    if not item:
        return None
    return Duel(pointer["side"]["S"], item)


def get_progress(user_id):
    """(experiência, vitórias, derrotas, existe registro)."""
    item = get_item(USER_PROGRESS_TABLE, {"userId": {"S": user_id}})
    if not item:
        return 0, 0, 0, False
    return (
        int(item.get("experience", {}).get("N", "0")),
        int(item.get("wins", {}).get("N", "0")),
        int(item.get("losses", {}).get("N", "0")),
        "experience" in item,
    )


# ---------------------------------------------------------------- gravação ---


def battle_put(duel):
    now = int(time.time())
    return {
        "TableName": PVP_BATTLES_TABLE,
        "Item": {
            "battleId": {"S": duel.battle_id},
            "status": {"S": duel.state["status"]},
            "version": {"N": str(duel.version + 1)},
            "state": {"S": json.dumps(duel.state)},
            "players": {"S": json.dumps(duel.players)},
            "updatedAt": {"S": datetime.fromtimestamp(now, timezone.utc).isoformat()},
            "expiresAt": {"N": str(now + BATTLE_TTL_SECONDS)},
            **pvp.listing_attributes(duel.state, duel.started_at),
        },
        # Impede que duas ações simultâneas usem a mesma vez.
        "ConditionExpression": "#version = :expected",
        "ExpressionAttributeNames": {"#version": "version"},
        "ExpressionAttributeValues": {":expected": {"N": str(duel.version)}},
    }


def save_active(duel):
    try:
        get_client().put_item(**battle_put(duel))
    except ClientError as error:
        if is_conditional_failure(error):
            raise BattleChanged() from error
        raise
    duel.version += 1


def side_result(duel, side, old_experience, wins, losses):
    state = duel.state
    gained = battle_experience(state, side)
    outcome = outcome_for(state, side)
    old_level, _ = level_for_experience(old_experience)
    new_experience = old_experience + gained
    new_level, _ = level_for_experience(new_experience)
    return {
        "outcome": outcome,
        "reason": view_reason(state["endReason"], outcome),
        "experienceGained": gained,
        "previousLevel": old_level,
        "level": new_level,
        "leveledUp": new_level > old_level,
        "shardsReward": level_up_reward(old_level, new_level),
        "progress": public_progress(
            new_experience,
            wins=wins + (1 if outcome == "won" else 0),
            losses=losses + (1 if outcome == "lost" else 0),
        ),
    }, old_experience, new_experience


def finish(duel):
    """Grava o fim do duelo e a experiência/recompensa dos dois numa só transação."""
    now = int(time.time())
    for _ in range(FINISH_ATTEMPTS):
        results = {}
        progress_updates = []
        wallet_updates = []
        for side in SIDES:
            user_id = duel.players[side]["userId"]
            old_experience, wins, losses, has_record = get_progress(user_id)
            result, old_xp, new_xp = side_result(duel, side, old_experience, wins, losses)
            results[side] = result
            progress_updates.append(
                {
                    "Update": {
                        "TableName": USER_PROGRESS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET experience = :new ADD wins :wins, losses :losses",
                        # Outra batalha pode ter terminado ao mesmo tempo: só grava
                        # se a experiência ainda for a que foi lida.
                        "ConditionExpression": (
                            "experience = :old" if has_record else "attribute_not_exists(experience)"
                        ),
                        "ExpressionAttributeValues": {
                            ":new": {"N": str(new_xp)},
                            ":wins": {"N": "1" if result["outcome"] == "won" else "0"},
                            ":losses": {"N": "1" if result["outcome"] == "lost" else "0"},
                            **({":old": {"N": str(old_xp)}} if has_record else {}),
                        },
                    }
                }
            )
            if result["shardsReward"]:
                wallet_updates.append(
                    {
                        "Update": {
                            "TableName": USER_WALLET_TABLE,
                            "Key": {"userId": {"S": user_id}},
                            "UpdateExpression": "ADD balance :shards",
                            "ExpressionAttributeValues": {
                                ":shards": {"N": str(result["shardsReward"])}
                            },
                        }
                    }
                )

        duel.state["results"] = results
        pointer_updates = [
            {
                "Update": {
                    "TableName": PVP_PLAYERS_TABLE,
                    "Key": {"userId": {"S": duel.players[side]["userId"]}},
                    "UpdateExpression": "SET #status = :finished, expiresAt = :expires",
                    "ConditionExpression": "battleId = :battleId",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":finished": {"S": "finished"},
                        ":expires": {"N": str(now + FINISHED_POINTER_TTL_SECONDS)},
                        ":battleId": {"S": duel.battle_id},
                    },
                }
            }
            for side in SIDES
        ]
        items = [
            {"Put": battle_put(duel)},
            *progress_updates,
            *pointer_updates,
            *wallet_updates,
        ]
        try:
            get_client().transact_write_items(TransactItems=items)
        except ClientError as error:
            failed = get_failed_conditions(error)
            if BATTLE_ITEM in failed:
                raise BattleChanged() from error
            if failed & PROGRESS_ITEMS:
                continue
            raise
        duel.version += 1
        return

    raise BattleChanged()


def store(duel):
    if duel.state["status"] == "active":
        save_active(duel)
    else:
        finish(duel)


# ------------------------------------------------------------------- rotas ---


def duel_response(status_code, duel, since):
    now = int(time.time())
    events, complete = pvp.events_since(duel.state, since, duel.side)
    return response(
        status_code,
        {
            "battle": pvp.public_duel(duel.state, duel.side, now, duel.public_players()),
            "events": events,
            "complete": complete,
            "result": duel.state.get("results", {}).get(duel.side),
        },
    )


def unchanged_response(duel):
    """Nada mudou desde o lote que o cliente tem: só o tempo de turno."""
    now = int(time.time())
    return response(
        200,
        {
            "unchanged": True,
            "battle": {
                "battleId": duel.battle_id,
                "seq": duel.state["seq"],
                "status": duel.state["status"],
                "turnSecondsLeft": pvp.turn_seconds_left(duel.state, now),
            },
        },
    )


def current(user_id, event):
    params = event.get("queryStringParameters") or {}
    since = parse_since(params.get("since"))
    battle_id = params.get("battleId")
    if battle_id is not None and not is_short_string(battle_id):
        return response(400, {"message": "Invalid duel."})
    try:
        duel = load_duel(user_id, battle_id)
        if duel is None:
            if battle_id is not None:
                return response(404, {"message": "Duel not found."})
            return response(200, {"battle": None, "events": [], "complete": True, "result": None})
        if duel.state["status"] == "active" and pvp.resolve_timeouts(
            duel.state, int(time.time()), new_rng()
        ):
            try:
                store(duel)
            except BattleChanged:
                # Outra requisição gravou antes: mostra o que está salvo.
                duel = load_duel(user_id, battle_id)
    except ClientError:
        return response(500, {"message": "Could not load the duel."})
    if since is not None and since == duel.state["seq"]:
        return unchanged_response(duel)
    return duel_response(200, duel, since)


def watch(user_id, event):
    params = event.get("queryStringParameters") or {}
    since = parse_since(params.get("since"))
    battle_id = params.get("battleId")
    if not is_short_string(battle_id):
        return response(400, {"message": "Invalid duel."})
    try:
        item = get_item(PVP_BATTLES_TABLE, {"battleId": {"S": battle_id}})
    except ClientError:
        return response(500, {"message": "Could not load the duel."})
    if not item:
        return response(404, {"message": "This duel is over or no longer exists."})
    duel = Duel(None, item)
    if duel.has_player(user_id):
        return response(409, {"message": "You are playing this duel.", "battleId": battle_id})
    if since is not None and since == duel.state["seq"]:
        return unchanged_response(duel)

    now = int(time.time())
    players = duel.public_players()
    events, complete = pvp.events_since(duel.state, since, SPECTATOR)
    return response(
        200,
        {
            "battle": pvp.public_spectator(duel.state, now, players),
            "events": events,
            "complete": complete,
            "result": pvp.spectator_result(duel.state, players),
        },
    )


def act(user_id, event):
    try:
        body = parse_body(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    battle_id = body.get("battleId")
    action_type = body.get("type")
    if not is_short_string(battle_id) or action_type not in ACTION_TYPES:
        return response(400, {"message": "Invalid action."})
    since = parse_since(body.get("since"))

    try:
        duel = load_duel(user_id, battle_id)
    except ClientError:
        return response(500, {"message": "Could not play the turn."})
    if duel is None or duel.battle_id != battle_id:
        return response(404, {"message": "Duel not found."})
    if duel.state["status"] != "active":
        return response(409, {"message": "This duel is over."})

    action = {"type": action_type}
    if action_type == "skill":
        skill = body.get("skill")
        target = body.get("target")
        if not is_short_string(skill) or not (target is None or is_short_string(target)):
            return response(400, {"message": "Invalid action."})
        # O cliente vê o próprio time como "p"; aqui volta para o id real.
        action.update(skill=skill, target=view_id(target, duel.side))

    now = int(time.time())
    rng = new_rng()
    if pvp.resolve_timeouts(duel.state, now, rng):
        # Uma vez acabou antes da ação chegar: grava o automático e não usa a
        # ação (ela era para uma vez que já passou).
        try:
            store(duel)
        except (ClientError, BattleChanged):
            pass
        return response(409, {"message": "Time ran out. The turn was played automatically."})

    try:
        pvp.play(duel.state, action, duel.side, now, rng)
    except BattleError as error:
        status = 400 if pvp.turn_side(duel.state) == duel.side else 409
        return response(status, {"message": str(error)})

    try:
        store(duel)
    except BattleChanged:
        return response(409, {"message": "The duel changed. Reload it."})
    except ClientError:
        return response(500, {"message": "Could not play the turn."})
    return duel_response(200, duel, since)


def lambda_handler(event, context):
    method = event.get("httpMethod")
    if method == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    resource = event.get("resource")
    if method == "GET" and resource == BATTLE_ROUTE:
        return current(user_id, event)
    if method == "POST" and resource == ACTION_ROUTE:
        return act(user_id, event)
    if method == "GET" and resource == WATCH_ROUTE:
        return watch(user_id, event)
    return response(404, {"message": "Not found."})
