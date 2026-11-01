import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

USER_CARDS_TABLE = os.environ.get("USER_CARDS_TABLE")
FILE_NAME_PATTERN = re.compile(r"^[a-z0-9_\-]+\.(jfif|jpg|jpeg|png|webp)$")


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


def parse_card(body):
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError("Corpo da requisição inválido.") from error

    if not isinstance(body, dict):
        raise ValueError("Corpo da requisição inválido.")

    card = body.get("card", body)

    if not isinstance(card, dict):
        raise ValueError("Carta inválida.")

    name = card.get("name")
    rarity = card.get("rarity")
    file_name = card.get("file_name")

    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise ValueError("Nome da carta inválido.")

    if not isinstance(rarity, int) or isinstance(rarity, bool) or not 1 <= rarity <= 5:
        raise ValueError("Raridade da carta inválida.")

    if not isinstance(file_name, str) or not FILE_NAME_PATTERN.match(file_name):
        raise ValueError("Arquivo da carta inválido.")

    return {
        "name": name.strip(),
        "rarity": rarity,
        "file_name": file_name,
    }


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {})

    user_id = get_user_id(event)
    if not user_id:
        return response(401, {"message": "Usuário não autenticado."})

    try:
        card = parse_card(event.get("body"))
    except ValueError as error:
        return response(400, {"message": str(error)})

    item = {
        "userId": user_id,
        "ownedCardId": str(uuid.uuid4()),
        "obtainedAt": datetime.now(timezone.utc).isoformat(),
        **card,
    }

    try:
        table = boto3.resource("dynamodb").Table(USER_CARDS_TABLE)
        table.put_item(Item=item)
    except ClientError:
        return response(500, {"message": "Não foi possível guardar a carta."})

    return response(201, {"card": item})
