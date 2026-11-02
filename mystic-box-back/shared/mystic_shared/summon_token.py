"""Token assinado que comprova um sorteio feito pelo servidor.

O `open_box` sorteia as cartas e devolve, junto delas, um token assinado com
HMAC-SHA256 contendo os `file_name` sorteados. Para guardar as cartas, o
frontend envia só esse token ao `save_user_card`, que confere a assinatura e a
validade e busca os dados das cartas em `cards.CHARACTERS`. Assim o cliente não
consegue inventar cartas nem alterar o resultado do sorteio.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid

import boto3

SUMMON_TOKEN_SECRET_ARN = os.environ.get("SUMMON_TOKEN_SECRET_ARN")

# Tempo para o visitante entrar/criar conta e guardar as cartas sorteadas.
TOKEN_TTL_SECONDS = int(os.environ.get("SUMMON_TOKEN_TTL_SECONDS", "1800"))

TOKEN_VERSION = 1

# Lido uma vez por container e reaproveitado entre invocações.
_secret = None


class InvalidSummonToken(Exception):
    pass


class ExpiredSummonToken(InvalidSummonToken):
    pass


def _get_secret():
    global _secret
    if _secret is None:
        result = boto3.client("secretsmanager").get_secret_value(
            SecretId=SUMMON_TOKEN_SECRET_ARN
        )
        _secret = result["SecretString"].encode()
    return _secret


def _b64encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(encoded_payload):
    return hmac.new(_get_secret(), encoded_payload.encode(), hashlib.sha256).digest()


def issue(file_names, now=None):
    """Gera o token de um sorteio com as cartas `file_names`."""
    now = int(time.time()) if now is None else now
    payload = {
        "v": TOKEN_VERSION,
        "id": uuid.uuid4().hex,
        "cards": list(file_names),
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return f"{encoded}.{_b64encode(_sign(encoded))}"


def verify(token, now=None):
    """Confere o token e devolve o conteúdo (`id`, `cards`, `exp`)."""
    if not isinstance(token, str) or token.count(".") != 1 or len(token) > 2048:
        raise InvalidSummonToken("Sorteio inválido.")

    encoded, signature = token.split(".")

    try:
        valid = hmac.compare_digest(_b64decode(signature), _sign(encoded))
        payload = json.loads(_b64decode(encoded)) if valid else None
    except (ValueError, TypeError) as error:
        raise InvalidSummonToken("Sorteio inválido.") from error

    if (
        not isinstance(payload, dict)
        or payload.get("v") != TOKEN_VERSION
        or not isinstance(payload.get("id"), str)
        or not isinstance(payload.get("cards"), list)
        or not isinstance(payload.get("exp"), int)
    ):
        raise InvalidSummonToken("Sorteio inválido.")

    now = int(time.time()) if now is None else now
    if now >= payload["exp"]:
        raise ExpiredSummonToken("Este sorteio expirou.")

    return payload
