"""Começa batalhas contra o computador e executa as ações do jogador.

Rotas:
- POST /battles: {"team": [fileName x3], "difficulty"} começa uma batalha
  nova (uma batalha ativa anterior é abandonada, sem experiência). Com
  {"team", "campaign": {"region", "stage"}} começa uma fase da campanha (só se
  a fase anterior já foi vencida).
- POST /battles/current/actions: {"battleId", "type": "skill"|"auto"|"forfeit",
  "skill"?, "target"?} executa o turno da carta da vez.

O cliente só manda intenções e identificadores. Cartas, atributos, dano,
sorteios e recompensas são calculados aqui (mystic_shared.battle). Quando a
batalha acaba, gravar o resultado, somar a experiência, pagar a recompensa
de nível e, na campanha, marcar a fase vencida e pagar a primeira vitória
acontecem na mesma transação.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from mystic_shared.battle import (
    TEAM_SIZE,
    BattleError,
    battle_experience,
    create_battle,
    create_campaign_battle,
    mark_omen,
    new_rng,
    play_turn,
    public_state,
)
from mystic_shared.ascension import read_ascensions
from mystic_shared.campaign import (
    CampaignError,
    check_stage,
    epilogue,
    first_clear_reward,
    progress_from_item,
    stage_attribute,
    stage_setup,
)
from mystic_shared.cards import get_character
from mystic_shared.omens import OMEN_EXPERIENCE_BONUS, public_omen
from mystic_shared.progression import level_for_experience, level_up_reward, public_progress

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

BATTLES_TABLE = os.environ.get("BATTLES_TABLE")
USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
USER_PROGRESS_TABLE = os.environ.get("USER_PROGRESS_TABLE")
USER_WALLET_TABLE = os.environ.get("USER_WALLET_TABLE")
CARD_ASCENSIONS_TABLE = os.environ.get("CARD_ASCENSIONS_TABLE")
REGION_PROGRESS_TABLE = os.environ.get("REGION_PROGRESS_TABLE")

# Batalhas somem sozinhas (TTL) um dia depois da última ação.
BATTLE_TTL_SECONDS = 24 * 60 * 60

MAX_ID_LENGTH = 64
ACTION_TYPES = ("skill", "auto", "forfeit")

# Posições na transação de fim de batalha.
BATTLE_ITEM = 0
PROGRESS_ITEM = 1
FINISH_ATTEMPTS = 3

START_ROUTE = "/battles"
ACTION_ROUTE = "/battles/current/actions"

# Criado uma vez por container e reaproveitado entre invocações.
_client = None


class BattleChanged(Exception):
    """A batalha foi alterada por outra requisição ao mesmo tempo."""


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


# ------------------------------------------------------------------ leitura ---


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


def get_progress(user_id):
    """(experiência, vitórias, derrotas, existe registro)."""
    item = get_client().get_item(
        TableName=USER_PROGRESS_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")
    if not item:
        return 0, 0, 0, False
    return (
        int(item.get("experience", {}).get("N", "0")),
        int(item.get("wins", {}).get("N", "0")),
        int(item.get("losses", {}).get("N", "0")),
        "experience" in item,
    )


def get_campaign_progress(user_id):
    """{região: fases vencidas} do jogador."""
    item = get_client().get_item(
        TableName=REGION_PROGRESS_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")
    return progress_from_item(item)


def get_battle_item(user_id):
    return get_client().get_item(
        TableName=BATTLES_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")


# ---------------------------------------------------------------- gravação ---


def battle_put(user_id, state, version, expected_version):
    now = int(time.time())
    put = {
        "TableName": BATTLES_TABLE,
        "Item": {
            "userId": {"S": user_id},
            "battleId": {"S": state["battleId"]},
            "status": {"S": state["status"]},
            "version": {"N": str(version)},
            "state": {"S": json.dumps(state)},
            "updatedAt": {"S": datetime.fromtimestamp(now, timezone.utc).isoformat()},
            "expiresAt": {"N": str(now + BATTLE_TTL_SECONDS)},
        },
    }
    if expected_version is not None:
        # Impede que duas ações simultâneas usem o mesmo turno.
        put["ConditionExpression"] = "#version = :expected"
        put["ExpressionAttributeNames"] = {"#version": "version"}
        put["ExpressionAttributeValues"] = {":expected": {"N": str(expected_version)}}
    return put


def save_active_battle(user_id, state, expected_version):
    try:
        get_client().put_item(**battle_put(user_id, state, (expected_version or 0) + 1,
                                           expected_version))
    except ClientError as error:
        if is_conditional_failure(error):
            raise BattleChanged() from error
        raise


def finish_battle(user_id, state, expected_version):
    """Grava o fim da batalha e a experiência/recompensa numa só transação."""
    gained = battle_experience(state)
    won = state["status"] == "won"
    campaign = state.get("campaign")

    for _ in range(FINISH_ATTEMPTS):
        old_experience, wins, losses, has_record = get_progress(user_id)
        old_level, _ = level_for_experience(old_experience)
        new_experience = old_experience + gained
        new_level, _ = level_for_experience(new_experience)
        shards = level_up_reward(old_level, new_level)

        # Campanha: a primeira vitória numa fase paga a recompensa dela.
        first_clear = False
        if campaign and won:
            cleared = get_campaign_progress(user_id).get(campaign["region"], 0)
            first_clear = cleared < campaign["stage"]
        campaign_reward = first_clear_reward(campaign["stage"]) if first_clear else 0

        progress_update = {
            "TableName": USER_PROGRESS_TABLE,
            "Key": {"userId": {"S": user_id}},
            "UpdateExpression": "SET experience = :new ADD wins :wins, losses :losses",
            # Outra batalha pode ter terminado ao mesmo tempo: só grava se a
            # experiência ainda for a que foi lida (senão lê de novo).
            "ConditionExpression": (
                "experience = :old" if has_record else "attribute_not_exists(experience)"
            ),
            "ExpressionAttributeValues": {
                ":new": {"N": str(new_experience)},
                ":wins": {"N": "1" if won else "0"},
                ":losses": {"N": "0" if won else "1"},
                **({":old": {"N": str(old_experience)}} if has_record else {}),
            },
        }
        items = [
            {"Put": battle_put(user_id, state, (expected_version or 0) + 1, expected_version)},
            {"Update": progress_update},
        ]
        if shards + campaign_reward:
            items.append(
                {
                    "Update": {
                        "TableName": USER_WALLET_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "ADD balance :shards",
                        "ExpressionAttributeValues": {
                            ":shards": {"N": str(shards + campaign_reward)}
                        },
                    }
                }
            )
        campaign_item = None
        if first_clear:
            campaign_item = len(items)
            items.append(
                {
                    "Update": {
                        "TableName": REGION_PROGRESS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET #stage = :stage",
                        # Só a primeira vitória paga: se outra requisição já
                        # marcou a fase, lê de novo (e não paga de novo).
                        "ConditionExpression": (
                            "attribute_not_exists(#stage) OR #stage < :stage"
                        ),
                        "ExpressionAttributeNames": {
                            "#stage": stage_attribute(campaign["region"])
                        },
                        "ExpressionAttributeValues": {
                            ":stage": {"N": str(campaign["stage"])}
                        },
                    }
                }
            )

        try:
            get_client().transact_write_items(TransactItems=items)
        except ClientError as error:
            failed = get_failed_conditions(error)
            if BATTLE_ITEM in failed:
                raise BattleChanged() from error
            if PROGRESS_ITEM in failed or (campaign_item is not None and campaign_item in failed):
                continue
            raise

        return {
            "outcome": state["status"],
            "reason": state["endReason"],
            "experienceGained": gained,
            "previousLevel": old_level,
            "level": new_level,
            "leveledUp": new_level > old_level,
            "shardsReward": shards,
            "campaign": (
                {
                    "region": campaign["region"],
                    "stage": campaign["stage"],
                    "boss": campaign["boss"],
                    "firstClear": first_clear,
                    "reward": campaign_reward,
                    # Vencer o chefe revela o epílogo da região.
                    "epilogue": epilogue(campaign["region"]) if won and campaign["boss"] else None,
                }
                if campaign
                else None
            ),
            "progress": public_progress(
                new_experience,
                wins=wins + (1 if won else 0),
                losses=losses + (0 if won else 1),
            ),
        }

    raise BattleChanged()


def store_battle(user_id, state, expected_version):
    """Grava o estado; devolve o resultado se a batalha acabou."""
    if state["status"] == "active":
        save_active_battle(user_id, state, expected_version)
        return None
    return finish_battle(user_id, state, expected_version)


# ------------------------------------------------------------------- rotas ---


def start(user_id, event):
    try:
        body = parse_body(event)
    except ValueError as error:
        return response(400, {"message": str(error)})

    team = body.get("team")
    difficulty = body.get("difficulty")
    campaign = body.get("campaign")
    if (
        not isinstance(team, list)
        or len(team) != TEAM_SIZE
        or not all(is_short_string(name) for name in team)
    ):
        return response(400, {"message": f"Choose exactly {TEAM_SIZE} cards."})
    if campaign is not None:
        if (
            not isinstance(campaign, dict)
            or not is_short_string(campaign.get("region"))
            or not isinstance(campaign.get("stage"), int)
            or isinstance(campaign.get("stage"), bool)
        ):
            return response(400, {"message": "Choose a campaign stage."})
    elif not is_short_string(difficulty):
        return response(400, {"message": "Choose a difficulty."})

    # Só os identificadores vêm do cliente; as cartas são as do servidor.
    characters = [get_character(name) for name in team]
    if any(character is None for character in characters):
        return response(400, {"message": "Unknown card."})

    try:
        owned = get_owned_file_names(user_id)
        experience, _, _, _ = get_progress(user_id)
        ascensions = read_ascensions(get_client(), CARD_ASCENSIONS_TABLE, user_id)
        campaign_progress = get_campaign_progress(user_id) if campaign is not None else {}
    except ClientError:
        return response(500, {"message": "Could not start the battle."})

    missing = [c["name"] for c in characters if c["file_name"] not in owned]
    if missing:
        return response(
            409, {"message": f"{', '.join(missing)} is not in your collection."}
        )

    level, _ = level_for_experience(experience)
    try:
        if campaign is not None:
            region, stage = campaign["region"], campaign["stage"]
            check_stage(region, stage, campaign_progress.get(region, 0))
            state, events = create_campaign_battle(
                str(uuid.uuid4()), characters, level, stage_setup(region, stage, level),
                new_rng(), ascensions=ascensions,
            )
        else:
            state, events = create_battle(
                str(uuid.uuid4()), characters, level, difficulty, new_rng(),
                ascensions=ascensions,
            )
    except (BattleError, CampaignError) as error:
        return response(400, {"message": str(error)})

    # Boato da semana: carta da região em destaque rende mais experiência.
    omen = public_omen()
    events = events + mark_omen(state, omen["region"], OMEN_EXPERIENCE_BONUS, omen["title"])

    try:
        result = store_battle(user_id, state, None)
    except (ClientError, BattleChanged):
        return response(500, {"message": "Could not start the battle."})

    return response(
        201, {"battle": public_state(state), "events": events, "result": result}
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
    action = {"type": action_type}
    if action_type == "skill":
        skill = body.get("skill")
        target = body.get("target")
        if not is_short_string(skill) or not (target is None or is_short_string(target)):
            return response(400, {"message": "Invalid action."})
        action.update(skill=skill, target=target)

    try:
        item = get_battle_item(user_id)
    except ClientError:
        return response(500, {"message": "Could not play the turn."})

    if not item or item["battleId"]["S"] != battle_id:
        return response(404, {"message": "Battle not found."})

    state = json.loads(item["state"]["S"])
    version = int(item["version"]["N"])
    if state["status"] != "active":
        return response(409, {"message": "This battle is over."})

    try:
        events = play_turn(state, action, new_rng())
    except BattleError as error:
        return response(400, {"message": str(error)})

    try:
        result = store_battle(user_id, state, version)
    except BattleChanged:
        return response(
            409, {"message": "The battle changed in another window. Reload it."}
        )
    except ClientError:
        return response(500, {"message": "Could not play the turn."})

    return response(
        200, {"battle": public_state(state), "events": events, "result": result}
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "User is not authenticated."})

    resource = event.get("resource")
    if resource == START_ROUTE:
        return start(user_id, event)
    if resource == ACTION_ROUTE:
        return act(user_id, event)
    return response(404, {"message": "Not found."})
