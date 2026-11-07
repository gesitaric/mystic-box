"""Regras do nome de usuário (username).

Fonte única: tamanho, caracteres permitidos, tempo de espera entre trocas e
regras da busca. As Lambdas validam por aqui e o frontend só exibe o que a API
devolve.
"""

import re

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
# Letras sem acento, números e "_". Precisa começar com letra.
USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
USERNAME_ALLOWED_DESCRIPTION = (
    "Letters (A-Z), numbers and underscore (_). Must start with a letter."
)

# Depois de definir/trocar o nome, espera para trocar de novo.
USERNAME_CHANGE_COOLDOWN_DAYS = 30
USERNAME_CHANGE_COOLDOWN_SECONDS = USERNAME_CHANGE_COOLDOWN_DAYS * 24 * 60 * 60

# Busca de jogadores: prefixo do nome, sem diferenciar maiúsculas.
SEARCH_MIN_LENGTH = 2
SEARCH_MAX_RESULTS = 20

# Limite de buscas por jogador: no máximo SEARCH_RATE_LIMIT_MAX buscas em
# cada janela fixa de SEARCH_RATE_LIMIT_WINDOW_SECONDS segundos.
SEARCH_RATE_LIMIT_MAX = 10
SEARCH_RATE_LIMIT_WINDOW_SECONDS = 60

# Chave de partição fixa do índice de busca (todos os nomes no mesmo índice,
# ordenados pelo nome em minúsculas).
SEARCH_PARTITION = "USERNAME"


def normalize(username):
    """Forma usada para unicidade e busca (sem diferenciar maiúsculas)."""
    return username.lower()


def validate_username(value):
    """Devolve (nome, None) se válido ou (None, mensagem de erro)."""
    if not isinstance(value, str):
        return None, "Enter a username."
    username = value.strip()
    if len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
        return None, (
            f"Usernames must have {USERNAME_MIN_LENGTH} to "
            f"{USERNAME_MAX_LENGTH} characters."
        )
    if not USERNAME_PATTERN.match(username):
        return None, f"Invalid username. {USERNAME_ALLOWED_DESCRIPTION}"
    return username, None


def normalize_search(value):
    """Prefixo de busca válido (minúsculas) ou None."""
    if not isinstance(value, str):
        return None
    query = value.strip()
    if len(query) < SEARCH_MIN_LENGTH or len(query) > USERNAME_MAX_LENGTH:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]+", query):
        return None
    return normalize(query)


def search_window(now):
    """Início da janela de limite de buscas e segundos até a próxima."""
    now = int(now)
    start = now - now % SEARCH_RATE_LIMIT_WINDOW_SECONDS
    return start, start + SEARCH_RATE_LIMIT_WINDOW_SECONDS - now


def change_status(changed_at, now):
    """Se o nome pode ser trocado agora e quanto falta, a partir da última troca."""
    if changed_at is None:
        return {"canChange": True, "retryAfterSeconds": 0, "nextChangeAt": None}
    next_change = int(changed_at) + USERNAME_CHANGE_COOLDOWN_SECONDS
    remaining = max(0, next_change - int(now))
    return {
        "canChange": remaining == 0,
        "retryAfterSeconds": remaining,
        "nextChangeAt": next_change if remaining else None,
    }


def public_rules():
    """Regras do nome para o formulário exibir."""
    return {
        "minLength": USERNAME_MIN_LENGTH,
        "maxLength": USERNAME_MAX_LENGTH,
        "allowed": USERNAME_ALLOWED_DESCRIPTION,
        "changeCooldownDays": USERNAME_CHANGE_COOLDOWN_DAYS,
        "searchMinLength": SEARCH_MIN_LENGTH,
        "searchRateLimit": {
            "maxSearches": SEARCH_RATE_LIMIT_MAX,
            "windowSeconds": SEARCH_RATE_LIMIT_WINDOW_SECONDS,
        },
    }
