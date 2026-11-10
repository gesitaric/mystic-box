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
"""

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
    }
