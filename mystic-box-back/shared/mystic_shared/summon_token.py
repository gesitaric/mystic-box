"""Token assinado que comprova um sorteio feito pelo servidor.

O `open_box` sorteia as cartas e devolve, junto delas, um token assinado com
HMAC-SHA256 contendo os `file_name` sorteados e o jogador (`uid`). Para guardar
as cartas, o frontend envia só esse token ao `save_user_card`, que confere a
assinatura, a validade e o dono e busca os dados das cartas em
`cards.CHARACTERS`. Assim o cliente não consegue inventar cartas, alterar o
resultado do sorteio nem guardar o sorteio de outro jogador.

O sorteio fica pendente no item do jogador em `UserSummonStateTable`
(`pendingToken`) até ser guardado ou expirar: abrir o portal de novo devolve o
mesmo sorteio, então não dá para sortear várias vezes e guardar só o melhor.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid

import boto3

from .cards import get_character, public_card

# Nome do parâmetro SecureString no SSM Parameter Store com a chave HMAC.
SUMMON_TOKEN_PARAMETER = os.environ.get("SUMMON_TOKEN_PARAMETER")

# Tempo para guardar as cartas sorteadas.
TOKEN_TTL_SECONDS = int(os.environ.get("SUMMON_TOKEN_TTL_SECONDS", "1800"))

# 2: o token leva o jogador (`uid`).
TOKEN_VERSION = 2

# Lido uma vez por container e reaproveitado entre invocações.
_secret = None


class InvalidSummonToken(Exception):
    pass


class ExpiredSummonToken(InvalidSummonToken):
    pass


def _get_secret():
    global _secret
    if _secret is None:
        result = boto3.client("ssm").get_parameter(
            Name=SUMMON_TOKEN_PARAMETER, WithDecryption=True
        )
        _secret = result["Parameter"]["Value"].encode()
    return _secret


def _b64encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(encoded_payload):
    return hmac.new(_get_secret(), encoded_payload.encode(), hashlib.sha256).digest()


def issue(file_names, user_id, now=None):
    """Gera o token de um sorteio com as cartas `file_names` para `user_id`."""
    now = int(time.time()) if now is None else now
    payload = {
        "v": TOKEN_VERSION,
        "id": uuid.uuid4().hex,
        "uid": user_id,
        "cards": list(file_names),
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{encoded}.{_b64encode(_sign(encoded))}"


def verify(token, now=None):
    """Confere o token e devolve o conteúdo (`id`, `uid`, `cards`, `iat`, `exp`)."""
    if not isinstance(token, str) or token.count(".") != 1 or len(token) > 2048:
        raise InvalidSummonToken("Invalid summon.")

    encoded, signature = token.split(".")

    try:
        valid = hmac.compare_digest(_b64decode(signature), _sign(encoded))
        payload = json.loads(_b64decode(encoded)) if valid else None
    except (ValueError, TypeError) as error:
        raise InvalidSummonToken("Invalid summon.") from error

    if (
        not isinstance(payload, dict)
        or payload.get("v") != TOKEN_VERSION
        or not isinstance(payload.get("id"), str)
        or not isinstance(payload.get("uid"), str)
        or not isinstance(payload.get("cards"), list)
        or not isinstance(payload.get("iat"), int)
        or not isinstance(payload.get("exp"), int)
    ):
        raise InvalidSummonToken("Invalid summon.")

    now = int(time.time()) if now is None else now
    if now >= payload["exp"]:
        raise ExpiredSummonToken("This summon has expired.")

    return payload


def pending_summon(item, user_id, now=None):
    """Sorteio pendente (ainda válido) no item de `UserSummonStateTable`, ou None.

    Devolve `{"cards", "summonToken"}` como o `POST /box/open` responde.
    """
    token = (item or {}).get("pendingToken", {}).get("S")
    if not token:
        return None
    try:
        payload = verify(token, now=now)
    except InvalidSummonToken:
        return None
    characters = [get_character(file_name) for file_name in payload["cards"]]
    if payload["uid"] != user_id or any(c is None for c in characters):
        return None
    return {
        "cards": [public_card(character) for character in characters],
        "summonToken": token,
    }
