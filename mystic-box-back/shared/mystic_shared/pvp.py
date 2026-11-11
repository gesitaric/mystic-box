"""Regras do duelo online (jogador contra jogador).

A batalha em si usa as mesmas regras de `battle.py` (mode "pvp"). Aqui ficam
as regras do que é só do online:

- Desafio: quem desafia precisa ter nome de usuário e encontra o adversário
  pelo nome. O desafio leva o time de quem desafia e expira em
  CHALLENGE_TTL_SECONDS. O adversário aceita (escolhendo o time dele) ou
  recusa; quem desafiou pode cancelar.
- Um duelo ativo por jogador.
- Tempo de turno: cada vez tem TURN_SECONDS. Se acabar, o servidor joga a
  carta no automático (como o "auto") e conta uma vez perdida. Quem perde
  MAX_MISSED_TURNS vezes seguidas abandona o duelo (derrota, sem experiência).
- Registro de eventos: cada ação gera um lote numerado (`seq`) que os dois
  jogadores buscam para animar; só os últimos EVENT_HISTORY lotes ficam
  guardados.
- Quem está online: quem tem nome de usuário e abre a tela de duelo aparece
  na lista do salão (LOBBY_ID). O cliente renova a presença a cada
  LOBBY_REFRESH_SECONDS; sem sinal por PRESENCE_SECONDS, o jogador some da
  lista. A lista mostra no máximo MAX_ONLINE_PLAYERS jogadores.
- Assistir: qualquer jogador com sessão pode assistir a um duelo em andamento
  (até MAX_LIVE_DUELS aparecem na lista). Quem assiste só lê: não joga vezes
  vencidas nem grava nada. Um duelo cuja vez venceu há mais de
  LIVE_DUEL_GRACE_SECONDS sai da lista (os dois jogadores saíram).
- Reações: os dois jogadores e quem assiste podem mandar reações durante o
  duelo, só com os emojis de REACTIONS (nada de texto livre). Cada pessoa
  espera REACTION_COOLDOWN_SECONDS entre uma e outra e manda no máximo
  MAX_REACTIONS_PER_WINDOW a cada REACTION_WINDOW_SECONDS. Reações não mexem
  na batalha (nem na vez, nem no tempo de turno) e somem depois de
  REACTION_TTL_SECONDS; não entram no histórico do duelo.
"""

import math

from . import battle

CHALLENGE_TTL_SECONDS = 10 * 60
MAX_OUTGOING_CHALLENGES = 5
TURN_SECONDS = 60
MAX_MISSED_TURNS = 3
EVENT_HISTORY = 40

SIDES = ("player", "enemy")

LOBBY_ID = "main"
LOBBY_REFRESH_SECONDS = 20
PRESENCE_SECONDS = 60
MAX_ONLINE_PLAYERS = 50
MAX_LIVE_DUELS = 20
LIVE_DUEL_GRACE_SECONDS = 30

# Reações (id, emoji). O cliente só manda o id; o emoji sai daqui.
REACTIONS = (
    ("clap", "👏"),
    ("fire", "🔥"),
    ("laugh", "😂"),
    ("wow", "😮"),
    ("sweat", "😅"),
    ("cry", "😢"),
    ("angry", "😠"),
    ("gg", "🤝"),
)
REACTION_EMOJIS = dict(REACTIONS)
REACTION_COOLDOWN_SECONDS = 2
REACTION_WINDOW_SECONDS = 30
MAX_REACTIONS_PER_WINDOW = 8
REACTION_TTL_SECONDS = 60
# Reações devolvidas por consulta (as mais recentes).
MAX_REACTIONS_PER_POLL = 20
# O cursor devolvido fica um pouco para trás do relógio do servidor, para não
# perder uma reação gravada ao mesmo tempo por outra requisição. O cliente
# ignora as que já mostrou (pelo id).
REACTION_CURSOR_LAG_MS = 3000
SPECTATOR_SIDE = "spectator"


def challenge_active(expires_at, now):
    return int(expires_at) > int(now)


def opponent_side(side):
    return "enemy" if side == "player" else "player"


# ------------------------------------------------------------------ presença ---


def presence_expires_at(now):
    """Até quando o jogador aparece na lista sem renovar a presença."""
    return int(now) + PRESENCE_SECONDS


def is_online(expires_at, now):
    return int(expires_at) > int(now)


def online_list(entries, now):
    """Jogadores online, mais recentes primeiro, no máximo MAX_ONLINE_PLAYERS.

    `entries`: [{"username", "level", "title", "lastSeen", "expiresAt", ...}].
    """
    online = [entry for entry in entries if is_online(entry["expiresAt"], now)]
    online.sort(key=lambda entry: (-int(entry["lastSeen"]), entry["username"].lower()))
    return online[:MAX_ONLINE_PLAYERS]


# ------------------------------------------------------------------ relógio ---


def _reset_clock(state, now):
    active = state["status"] == "active" and state["turn"]
    state["turnDeadline"] = int(now) + TURN_SECONDS if active else None


def _record(state, events, now):
    state["seq"] += 1
    state["log"].append({"seq": state["seq"], "events": events})
    del state["log"][:-EVENT_HISTORY]
    _reset_clock(state, now)


def start_online(state, events, now):
    """Prepara o estado de uma batalha recém-criada para o duelo online."""
    state["seq"] = 0
    state["log"] = []
    state["missed"] = {side: 0 for side in SIDES}
    _record(state, events, now)


def turn_side(state):
    """Lado da carta da vez (None se ninguém estiver na vez)."""
    if state["status"] != "active" or not state["turn"]:
        return None
    return battle._unit(state, state["turn"])["side"]


def turn_seconds_left(state, now):
    deadline = state.get("turnDeadline")
    if deadline is None:
        return None
    return max(0, int(deadline) - int(now))


def resolve_timeouts(state, now, rng):
    """Joga no automático as vezes cujo tempo acabou. Devolve True se mudou algo."""
    changed = False
    while state["status"] == "active" and state["turn"]:
        deadline = state.get("turnDeadline")
        if deadline is None or int(now) < int(deadline):
            break
        side = turn_side(state)
        state["missed"][side] += 1
        events = [{"type": "timeout", "target": state["turn"]}]
        if state["missed"][side] >= MAX_MISSED_TURNS:
            battle.withdraw(state, side, "abandon", events)
        else:
            events += battle.play_turn(state, {"type": "auto"}, rng, side)
        _record(state, events, now)
        changed = True
    return changed


def play(state, action, side, now, rng):
    """Ação de um jogador. Lança battle.BattleError se for inválida."""
    events = battle.play_turn(state, action, rng, side)
    if action.get("type") != "forfeit":
        state["missed"][side] = 0
    _record(state, events, now)
    return events


# ------------------------------------------------------- duelos ao vivo ---


def listing_attributes(state, started_at):
    """Atributos do item do duelo lidos pela lista de duelos em andamento.

    Formato do DynamoDB. `liveIn` só existe enquanto o duelo está ativo, então
    o índice dos duelos em andamento (LiveDuelsIndex) só tem esses.
    """
    attributes = {
        "startedAt": {"N": str(int(started_at))},
        "round": {"N": str(state["round"])},
    }
    if state["status"] == "active":
        attributes["liveIn"] = {"S": LOBBY_ID}
    if state.get("turnDeadline") is not None:
        attributes["turnDeadline"] = {"N": str(int(state["turnDeadline"]))}
    return attributes


def is_live(turn_deadline, now):
    """Duelo com alguém jogando (a vez não venceu há muito tempo)."""
    if turn_deadline is None:
        return True
    return int(now) <= int(turn_deadline) + LIVE_DUEL_GRACE_SECONDS


def live_list(entries, now):
    """Duelos em andamento, mais recentes primeiro, no máximo MAX_LIVE_DUELS.

    `entries`: [{"startedAt", "turnDeadline", ...}].
    """
    live = [entry for entry in entries if is_live(entry.get("turnDeadline"), now)]
    live.sort(key=lambda entry: -int(entry["startedAt"]))
    return live[:MAX_LIVE_DUELS]


# ---------------------------------------------------------------- reações ---


class ReactionLimited(Exception):
    """Reação enviada antes da hora; `retry_after` em segundos."""

    def __init__(self, retry_after):
        super().__init__("Too many reactions. Wait a moment.")
        self.retry_after = max(1, int(retry_after))


def is_reaction(reaction_id):
    return isinstance(reaction_id, str) and reaction_id in REACTION_EMOJIS


def reaction_quota(sender, now_ms):
    """Novo controle de envio de quem reage, ou ReactionLimited.

    `sender`: None (primeira reação) ou {"lastAt", "windowStart", "count"},
    com os instantes em milissegundos.
    """
    now_ms = int(now_ms)
    if sender is None:
        return {"lastAt": now_ms, "windowStart": now_ms, "count": 1}
    cooldown_ends = int(sender["lastAt"]) + REACTION_COOLDOWN_SECONDS * 1000
    if now_ms < cooldown_ends:
        raise ReactionLimited(math.ceil((cooldown_ends - now_ms) / 1000))
    window_ends = int(sender["windowStart"]) + REACTION_WINDOW_SECONDS * 1000
    if now_ms >= window_ends:
        return {"lastAt": now_ms, "windowStart": now_ms, "count": 1}
    if int(sender["count"]) >= MAX_REACTIONS_PER_WINDOW:
        raise ReactionLimited(math.ceil((window_ends - now_ms) / 1000))
    return {
        "lastAt": now_ms,
        "windowStart": int(sender["windowStart"]),
        "count": int(sender["count"]) + 1,
    }


def reaction_key(at_ms, nonce):
    """Chave de ordenação de uma reação (ordem de envio)."""
    return f"r#{int(at_ms):013d}#{nonce}"


def reaction_range(since_ms):
    """Faixa de chaves das reações enviadas depois de `since_ms`."""
    return reaction_key(int(since_ms) + 1, ""), "r#~"


def reaction_cursor(now_ms):
    return max(0, int(now_ms) - REACTION_CURSOR_LAG_MS)


def view_reaction(reaction, viewer_side, viewer_id):
    """Reação vista por quem pede.

    `reaction`: {"key", "reaction", "side", "username", "senderId"}; `side` é
    o lado guardado do jogador que reagiu ou SPECTATOR_SIDE. Para um jogador,
    o próprio lado é sempre "player" (como no resto do duelo); quem assiste
    (`viewer_side` None) vê os lados como estão guardados.
    """
    side = reaction["side"]
    if viewer_side is not None and side in SIDES:
        side = "player" if side == viewer_side else "enemy"
    return {
        "id": reaction["key"],
        "reaction": reaction["reaction"],
        "emoji": REACTION_EMOJIS.get(reaction["reaction"], ""),
        "side": side,
        "username": reaction.get("username"),
        "isYou": reaction["senderId"] == viewer_id,
    }


def recent_reactions(reactions, since_ms, now_ms, viewer_side, viewer_id):
    """Reações depois de `since_ms` ainda válidas, em ordem, vistas por quem pede.

    `reactions`: [{"key", "at", "expiresAt", ...}] (expiresAt em segundos).
    """
    now_seconds = int(now_ms) // 1000
    fresh = [
        reaction
        for reaction in reactions
        if int(reaction["at"]) > int(since_ms)
        and int(reaction["expiresAt"]) > now_seconds
        and reaction["reaction"] in REACTION_EMOJIS
    ]
    fresh.sort(key=lambda reaction: reaction["key"])
    return [
        view_reaction(reaction, viewer_side, viewer_id)
        for reaction in fresh[-MAX_REACTIONS_PER_POLL:]
    ]


def reaction_options():
    return [{"id": reaction_id, "emoji": emoji} for reaction_id, emoji in REACTIONS]


# ------------------------------------------------------------------- visão ---


def events_since(state, since, viewer):
    """(eventos depois do lote `since`, completo?) como `viewer` vê.

    Se `since` for mais antigo que o histórico guardado, devolve só os lotes
    que restam e completo=False (o cliente mostra o estado atual sem animar).
    """
    if since is None:
        return [], True
    log = state["log"]
    complete = not log or since >= log[0]["seq"] - 1
    events = [e for batch in log if batch["seq"] > since for e in batch["events"]]
    return battle.view_events(events, viewer), complete


def public_duel(state, side, now, players):
    """Batalha vista por `side`, com o tempo de turno e os nomes dos jogadores.

    `players`: {side: {"username", "level"}}.
    """
    view = battle.public_state(state, side)
    view["seq"] = state["seq"]
    view["turnSeconds"] = TURN_SECONDS
    view["turnSecondsLeft"] = turn_seconds_left(state, now)
    view["missedTurns"] = state["missed"][side]
    view["opponentMissedTurns"] = state["missed"][opponent_side(side)]
    view["maxMissedTurns"] = MAX_MISSED_TURNS
    view["you"] = players.get(side)
    view["opponent"] = players.get(opponent_side(side))
    view["reactionOptions"] = reaction_options()
    view["reactionCooldownSeconds"] = REACTION_COOLDOWN_SECONDS
    return view


def public_spectator(state, now, players):
    """Duelo visto por quem assiste: os dois lados como estão guardados.

    `players`: {side: {"username", "level", "title"}}.
    """
    view = battle.public_state(state, battle.SPECTATOR)
    view["spectating"] = True
    view["seq"] = state["seq"]
    view["turnSeconds"] = TURN_SECONDS
    view["turnSecondsLeft"] = turn_seconds_left(state, now)
    view["maxMissedTurns"] = MAX_MISSED_TURNS
    view["missedTurns"] = dict(state["missed"])
    view["players"] = {side: players.get(side) for side in SIDES}
    view["winner"] = battle.winner_side(state)
    view["reactionOptions"] = reaction_options()
    view["reactionCooldownSeconds"] = REACTION_COOLDOWN_SECONDS
    return view


def spectator_result(state, players):
    """Fim do duelo para quem assiste (None se ainda está em andamento)."""
    if state["status"] == "active":
        return None
    winner = battle.winner_side(state)
    return {
        "spectator": True,
        "outcome": "draw" if winner is None else "won",
        "winner": players[winner]["username"] if winner else None,
        "loser": players[opponent_side(winner)]["username"] if winner else None,
        "reason": state["endReason"],
    }


def public_rules():
    return {
        "teamSize": battle.TEAM_SIZE,
        "challengeTtlSeconds": CHALLENGE_TTL_SECONDS,
        "maxOutgoingChallenges": MAX_OUTGOING_CHALLENGES,
        "turnSeconds": TURN_SECONDS,
        "maxMissedTurns": MAX_MISSED_TURNS,
        "winExperience": battle.PVP["experience"],
        "lossExperience": round(battle.PVP["experience"] * battle.LOSS_EXPERIENCE_RATIO),
        "lossExperiencePerDefeat": battle.LOSS_EXPERIENCE_PER_DEFEAT,
        "maxRounds": battle.MAX_ROUNDS,
        "lobbyRefreshSeconds": LOBBY_REFRESH_SECONDS,
        "presenceSeconds": PRESENCE_SECONDS,
        "maxOnlinePlayers": MAX_ONLINE_PLAYERS,
        "maxLiveDuels": MAX_LIVE_DUELS,
        "reactions": reaction_options(),
        "reactionCooldownSeconds": REACTION_COOLDOWN_SECONDS,
        "reactionWindowSeconds": REACTION_WINDOW_SECONDS,
        "maxReactionsPerWindow": MAX_REACTIONS_PER_WINDOW,
        "reactionTtlSeconds": REACTION_TTL_SECONDS,
    }
