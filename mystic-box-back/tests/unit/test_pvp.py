import json
import random

import pytest
from mystic_shared import battle, pvp
from mystic_shared.cards import get_character

from pvp_battle import app as pvp_battle
from pvp_challenges import app as pvp_challenges
from tests.unit.fake_dynamo import FakeDynamo

ALICE = "alice-sub"
BOB = "bob-sub"
CAROL = "carol-sub"
ALICE_TEAM = ["rowan.jfif", "brina.jfif", "maelis.jfif"]
BOB_TEAM = ["pyralis.jfif", "malachar.jfif", "lyra.png"]

TABLES = {
    "challenges": ("opponentId", "challengerId"),
    "battles": ("battleId", None),
    "players": ("userId", None),
    "profiles": ("userId", None),
    "usernames": ("usernameLower", None),
    "cards": ("userId", "ownedCardId"),
    "progress": ("userId", None),
    "wallet": ("userId", None),
    "ascensions": ("userId", "file_name"),
}


@pytest.fixture()
def clock(monkeypatch):
    """Relógio controlado pelos testes (as duas Lambdas usam time.time)."""
    now = {"value": 1_000_000}
    for module in (pvp_battle, pvp_challenges):
        monkeypatch.setattr(module.time, "time", lambda: now["value"])
    return now


@pytest.fixture()
def db(monkeypatch, clock):
    fake = FakeDynamo(TABLES)
    for user_id, name in ((ALICE, "Alice"), (BOB, "Bob"), (CAROL, "Carol")):
        fake.tables["profiles"][(user_id, None)] = {
            "userId": {"S": user_id},
            "username": {"S": name},
            "usernameLower": {"S": name.lower()},
        }
        fake.tables["usernames"][(name.lower(), None)] = {
            "usernameLower": {"S": name.lower()},
            "userId": {"S": user_id},
        }
    for user_id, team in ((ALICE, ALICE_TEAM), (BOB, BOB_TEAM), (CAROL, ALICE_TEAM)):
        for index, name in enumerate(team):
            fake.tables["cards"][(user_id, f"{user_id}-{index}")] = {
                "userId": {"S": user_id},
                "ownedCardId": {"S": f"{user_id}-{index}"},
                "file_name": {"S": name},
            }

    env = {
        "PVP_CHALLENGES_TABLE": "challenges",
        "PVP_BATTLES_TABLE": "battles",
        "PVP_PLAYERS_TABLE": "players",
        "USER_PROFILES_TABLE": "profiles",
        "USERNAMES_TABLE": "usernames",
        "USER_CARDS_TABLE": "cards",
        "USER_PROGRESS_TABLE": "progress",
        "USER_WALLET_TABLE": "wallet",
        "CARD_ASCENSIONS_TABLE": "ascensions",
    }
    for module in (pvp_battle, pvp_challenges):
        monkeypatch.setattr(module, "_client", fake)
        monkeypatch.setattr(module, "new_rng", lambda: random.Random(7))
        for name, value in env.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
    return fake


def call(handler, event):
    ret = handler.lambda_handler(event, "")
    return ret["statusCode"], json.loads(ret["body"])


def request(authenticated_event, user, method, resource, body=None, query=None):
    return authenticated_event(
        sub=user,
        httpMethod=method,
        resource=resource,
        body=json.dumps(body) if body is not None else None,
        queryStringParameters=query,
    )


def lobby(authenticated_event, user):
    return call(pvp_challenges, request(authenticated_event, user, "GET", "/pvp"))


def challenge(authenticated_event, user, username, team):
    return call(
        pvp_challenges,
        request(authenticated_event, user, "POST", "/pvp/challenges",
                {"username": username, "team": team}),
    )


def accept(authenticated_event, user, challenge_id, team):
    return call(
        pvp_challenges,
        request(authenticated_event, user, "POST", "/pvp/challenges/accept",
                {"challengeId": challenge_id, "team": team}),
    )


def current(authenticated_event, user, since=None, battle_id=None):
    query = {}
    if since is not None:
        query["since"] = str(since)
    if battle_id is not None:
        query["battleId"] = battle_id
    return call(pvp_battle, request(authenticated_event, user, "GET", "/pvp/battle",
                                    query=query or None))


def act(authenticated_event, user, body):
    return call(
        pvp_battle,
        request(authenticated_event, user, "POST", "/pvp/battle/actions", body),
    )


def start_duel(authenticated_event):
    status, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    assert status == 201, body
    status, body = accept(authenticated_event, BOB, body["challenge"]["challengeId"], BOB_TEAM)
    assert status == 201, body
    return body["battleId"]


def stored_state(db, battle_id):
    return json.loads(db.tables["battles"][(battle_id, None)]["state"]["S"])


def whose_turn(authenticated_event):
    for user in (ALICE, BOB):
        _, body = current(authenticated_event, user)
        if body["battle"]["yourTurn"]:
            return user, body["battle"]
    raise AssertionError("Nobody is on turn.")


# ------------------------------------------------------------- motor ---


def characters(names):
    return [get_character(name) for name in names]


def new_duel(level_a=5, level_b=3):
    state, events = battle.create_pvp_battle(
        "b1", characters(ALICE_TEAM), level_a, characters(BOB_TEAM), level_b, random.Random(1)
    )
    return state, events


def test_pvp_battle_waits_for_either_player():
    state, events = new_duel()
    assert state["mode"] == "pvp"
    assert state["status"] == "active"
    assert state["turn"] is not None
    # Ninguém joga pelo outro: a batalha para na vez da primeira carta.
    assert not any(event["type"] == "skill" for event in events)
    levels = {u["side"]: u["level"] for u in state["units"]}
    assert levels == {"player": 5, "enemy": 3}


def test_pvp_units_have_no_difficulty_bonus():
    state, _ = new_duel(level_a=4, level_b=4)
    for unit in state["units"]:
        expected = battle.build_unit(get_character(unit["fileName"]), unit["side"], 0, 4)
        assert unit["stats"] == expected["stats"]


def test_pvp_only_the_side_on_turn_can_act():
    state, _ = new_duel()
    side = battle._unit(state, state["turn"])["side"]
    other = "enemy" if side == "player" else "player"
    with pytest.raises(battle.BattleError, match="not your turn"):
        battle.play_turn(state, {"type": "auto"}, random.Random(1), other)
    battle.play_turn(state, {"type": "auto"}, random.Random(1), side)


def test_pvp_view_flips_sides_for_the_opponent():
    state, _ = new_duel()
    view = battle.public_state(state, "enemy")
    own = [u for u in view["units"] if u["side"] == "player"]
    assert sorted(u["fileName"] for u in own) == sorted(BOB_TEAM)
    assert all(u["id"].startswith("p") for u in own)
    assert view["aether"] == {"player": state["aether"]["enemy"], "enemy": state["aether"]["player"]}
    assert view["turn"] == battle.view_id(state["turn"], "enemy")


def test_pvp_view_shows_actions_only_on_your_turn():
    state, _ = new_duel()
    side = battle._unit(state, state["turn"])["side"]
    other = "enemy" if side == "player" else "player"
    mine = battle.public_state(state, side)
    theirs = battle.public_state(state, other)
    assert mine["yourTurn"] and mine["actions"]
    assert not theirs["yourTurn"] and theirs["actions"] == []
    # Alvos vêm no ponto de vista de quem joga: inimigos sempre "e".
    strike = next(a for a in mine["actions"] if a["id"] == "strike")
    assert all(target.startswith("e") for target in strike["targets"])


def test_pvp_forfeit_by_either_side():
    state, _ = new_duel()
    events = battle.play_turn(state, {"type": "forfeit"}, random.Random(1), "enemy")
    assert state["status"] == "won"
    assert state["endReason"] == "forfeit"
    assert battle.outcome_for(state, "enemy") == "lost"
    assert battle.battle_experience(state, "enemy") == 0
    assert battle.battle_experience(state, "player") == battle.PVP["experience"]
    winner_view = battle.view_events(events, "player")
    loser_view = battle.view_events(events, "enemy")
    assert winner_view[-1]["result"] == "won"
    assert winner_view[-1]["reason"] == "opponent_forfeit"
    assert loser_view[-1] == {"type": "end", "result": "lost", "reason": "forfeit"}


def test_pvp_timeout_is_a_draw():
    state, _ = new_duel()
    state["round"] = battle.MAX_ROUNDS
    state["queue"] = []
    events = []
    battle._start_round(state, random.Random(1), events)
    assert state["status"] == "draw"
    loss = round(battle.PVP["experience"] * battle.LOSS_EXPERIENCE_RATIO)
    assert battle.battle_experience(state, "player") == loss
    assert battle.battle_experience(state, "enemy") == loss


def test_pve_timeout_is_still_a_loss():
    state, _ = battle.create_battle(
        "b2", characters(ALICE_TEAM), 5, "novice", random.Random(1)
    )
    state["round"] = battle.MAX_ROUNDS
    state["queue"] = []
    battle._start_round(state, random.Random(1), [])
    assert state["status"] == "lost"


def test_pvp_turn_timeout_plays_automatically_and_abandons():
    state, events = new_duel()
    pvp.start_online(state, events, 100)
    assert state["turnDeadline"] == 100 + pvp.TURN_SECONDS
    assert not pvp.resolve_timeouts(state, 100 + pvp.TURN_SECONDS - 1, random.Random(1))

    now = 100
    for _ in range(50):
        if state["status"] != "active":
            break
        now = state["turnDeadline"]
        pvp.resolve_timeouts(state, now, random.Random(1))
    assert state["status"] in ("won", "lost")
    assert state["endReason"] == "abandon"
    loser = "player" if state["status"] == "lost" else "enemy"
    assert state["missed"][loser] == pvp.MAX_MISSED_TURNS
    assert battle.battle_experience(state, loser) == 0
    assert any(e["type"] == "timeout" for batch in state["log"] for e in batch["events"])


def test_pvp_acting_resets_missed_turns():
    state, events = new_duel()
    pvp.start_online(state, events, 0)
    side = pvp.turn_side(state)
    state["missed"][side] = 2
    pvp.play(state, {"type": "auto"}, side, 10, random.Random(1))
    assert state["missed"][side] == 0


def test_events_since_keeps_a_limited_history(monkeypatch):
    monkeypatch.setattr(pvp, "EVENT_HISTORY", 3)
    state, events = new_duel()
    pvp.start_online(state, events, 0)
    for step in range(6):
        if state["status"] != "active":
            break
        pvp.play(state, {"type": "auto"}, pvp.turn_side(state), step, random.Random(step))
    assert len(state["log"]) <= pvp.EVENT_HISTORY
    _, complete = pvp.events_since(state, 0, "player")
    assert not complete
    latest, complete = pvp.events_since(state, state["seq"], "player")
    assert latest == [] and complete
    assert pvp.events_since(state, None, "player") == ([], True)


# --------------------------------------------------------- desafios ---


def test_pvp_requires_authentication(apigw_event):
    status, _ = call(pvp_challenges, dict(apigw_event, httpMethod="GET", resource="/pvp"))
    assert status == 401
    status, _ = call(pvp_battle, dict(apigw_event, httpMethod="GET", resource="/pvp/battle"))
    assert status == 401


def test_lobby_starts_empty(authenticated_event, db):
    status, body = lobby(authenticated_event, ALICE)
    assert status == 200
    assert body["hasUsername"] and body["username"] == "Alice"
    assert body["incoming"] == [] and body["outgoing"] == []
    assert body["battle"] is None
    assert body["rules"]["turnSeconds"] == pvp.TURN_SECONDS


def test_challenge_requires_a_username(authenticated_event, db):
    del db.tables["profiles"][(ALICE, None)]["username"]
    status, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    assert status == 409
    assert "username" in body["message"]
    assert db.tables["challenges"] == {}


def test_challenge_unknown_player(authenticated_event, db):
    status, _ = challenge(authenticated_event, ALICE, "nobody", ALICE_TEAM)
    assert status == 404
    status, _ = challenge(authenticated_event, ALICE, "!!", ALICE_TEAM)
    assert status == 404


def test_cannot_challenge_yourself(authenticated_event, db):
    status, _ = challenge(authenticated_event, ALICE, "ALICE", ALICE_TEAM)
    assert status == 400


def test_challenge_checks_card_ownership(authenticated_event, db):
    status, body = challenge(authenticated_event, ALICE, "bob", BOB_TEAM)
    assert status == 409
    assert "not in your collection" in body["message"]


@pytest.mark.parametrize(
    "team",
    [None, [], ALICE_TEAM[:2], ALICE_TEAM + ["x.png"], [ALICE_TEAM[0]] * 3, ["unknown.png"] * 3],
)
def test_challenge_rejects_invalid_teams(authenticated_event, db, team):
    status, _ = challenge(authenticated_event, ALICE, "bob", team)
    assert status == 400


def test_challenge_shows_up_for_both_players(authenticated_event, db):
    status, body = challenge(authenticated_event, ALICE, "Bob", ALICE_TEAM)
    assert status == 201
    assert body["challenge"]["username"] == "Bob"
    challenge_id = body["challenge"]["challengeId"]

    _, alice = lobby(authenticated_event, ALICE)
    _, bob = lobby(authenticated_event, BOB)
    assert [c["challengeId"] for c in alice["outgoing"]] == [challenge_id]
    assert [c["challengeId"] for c in bob["incoming"]] == [challenge_id]
    assert bob["incoming"][0]["username"] == "Alice"
    assert bob["incoming"][0]["level"] == 1
    # O id do Cognito do outro jogador não aparece.
    assert ALICE not in json.dumps(bob) and BOB not in json.dumps(alice)


def test_duplicate_challenge_is_rejected_until_it_expires(authenticated_event, db, clock):
    assert challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)[0] == 201
    assert challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)[0] == 409
    clock["value"] += pvp.CHALLENGE_TTL_SECONDS
    _, bob = lobby(authenticated_event, BOB)
    assert bob["incoming"] == []
    assert challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)[0] == 201


def test_outgoing_challenge_limit(authenticated_event, db, monkeypatch):
    monkeypatch.setattr(pvp, "MAX_OUTGOING_CHALLENGES", 1)
    assert challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)[0] == 201
    assert challenge(authenticated_event, ALICE, "carol", ALICE_TEAM)[0] == 429


def test_decline_and_cancel(authenticated_event, db):
    _, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    challenge_id = body["challenge"]["challengeId"]

    # Só quem foi desafiado recusa; só quem desafiou cancela.
    decline = request(authenticated_event, ALICE, "POST", "/pvp/challenges/decline",
                      {"challengeId": challenge_id})
    assert call(pvp_challenges, decline)[0] == 404
    cancel = request(authenticated_event, BOB, "POST", "/pvp/challenges/cancel",
                     {"challengeId": challenge_id})
    assert call(pvp_challenges, cancel)[0] == 404

    decline = request(authenticated_event, BOB, "POST", "/pvp/challenges/decline",
                      {"challengeId": challenge_id})
    assert call(pvp_challenges, decline)[0] == 200
    assert db.tables["challenges"] == {}

    _, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    cancel = request(authenticated_event, ALICE, "POST", "/pvp/challenges/cancel",
                     {"challengeId": body["challenge"]["challengeId"]})
    assert call(pvp_challenges, cancel)[0] == 200
    assert db.tables["challenges"] == {}


def test_only_the_challenged_player_can_accept(authenticated_event, db):
    _, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    challenge_id = body["challenge"]["challengeId"]
    assert accept(authenticated_event, ALICE, challenge_id, ALICE_TEAM)[0] == 404
    assert accept(authenticated_event, CAROL, challenge_id, ALICE_TEAM)[0] == 404


def test_accept_starts_the_duel(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    assert db.tables["challenges"] == {}
    pointers = {key[0]: item for key, item in db.tables["players"].items()}
    assert pointers[ALICE]["side"]["S"] == "player"
    assert pointers[BOB]["side"]["S"] == "enemy"
    assert {p["status"]["S"] for p in pointers.values()} == {"active"}

    state = stored_state(db, battle_id)
    assert state["mode"] == "pvp"
    alice_cards = [u["fileName"] for u in state["units"] if u["side"] == "player"]
    assert alice_cards == ALICE_TEAM

    _, alice = lobby(authenticated_event, ALICE)
    assert alice["battle"] == {"battleId": battle_id, "opponent": "Bob"}


def test_duel_uses_each_players_ascension(authenticated_event, db):
    for user_id, file_name, level in ((ALICE, ALICE_TEAM[0], 2), (BOB, BOB_TEAM[1], 1)):
        db.tables["ascensions"][(user_id, file_name)] = {
            "userId": {"S": user_id},
            "file_name": {"S": file_name},
            "ascension": {"N": str(level)},
        }

    state = stored_state(db, start_duel(authenticated_event))

    ascension = {(u["side"], u["fileName"]): u["ascension"] for u in state["units"]}
    assert ascension[("player", ALICE_TEAM[0])] == 2
    assert ascension[("player", ALICE_TEAM[1])] == 0
    assert ascension[("enemy", BOB_TEAM[1])] == 1


def test_accept_checks_both_teams(authenticated_event, db):
    _, body = challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)
    challenge_id = body["challenge"]["challengeId"]
    status, body = accept(authenticated_event, BOB, challenge_id, ALICE_TEAM)
    assert status == 409 and "not in your collection" in body["message"]

    # Quem desafiou vendeu uma carta do time: o desafio é cancelado.
    del db.tables["cards"][(ALICE, f"{ALICE}-0")]
    status, body = accept(authenticated_event, BOB, challenge_id, BOB_TEAM)
    assert status == 409 and "no longer has" in body["message"]
    assert db.tables["challenges"] == {}


def test_one_active_duel_per_player(authenticated_event, db):
    start_duel(authenticated_event)
    status, body = challenge(authenticated_event, ALICE, "carol", ALICE_TEAM)
    assert status == 409 and "current duel" in body["message"]

    _, body = challenge(authenticated_event, CAROL, "alice", ALICE_TEAM)
    assert accept(authenticated_event, ALICE, body["challenge"]["challengeId"], ALICE_TEAM)[0] == 409
    _, body = challenge(authenticated_event, CAROL, "bob", ALICE_TEAM)
    assert accept(authenticated_event, BOB, body["challenge"]["challengeId"], BOB_TEAM)[0] == 409


def test_stale_pointer_does_not_block(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    del db.tables["battles"][(battle_id, None)]  # TTL
    assert challenge(authenticated_event, ALICE, "carol", ALICE_TEAM)[0] == 201


# ----------------------------------------------------------- duelo ---


def test_current_without_duel(authenticated_event, db):
    status, body = current(authenticated_event, ALICE)
    assert status == 200
    assert body["battle"] is None


def test_both_players_see_their_own_side(authenticated_event, db):
    start_duel(authenticated_event)
    _, alice = current(authenticated_event, ALICE, since=0)
    _, bob = current(authenticated_event, BOB, since=0)

    def own(view):
        return sorted(u["fileName"] for u in view["battle"]["units"] if u["side"] == "player")

    assert own(alice) == sorted(ALICE_TEAM)
    assert own(bob) == sorted(BOB_TEAM)
    assert alice["battle"]["opponent"]["username"] == "Bob"
    assert bob["battle"]["opponent"]["username"] == "Alice"
    assert alice["battle"]["yourTurn"] != bob["battle"]["yourTurn"]
    assert alice["events"] and alice["events"][0]["type"] == "round"
    assert alice["battle"]["turnSecondsLeft"] == pvp.TURN_SECONDS


def test_action_only_on_your_turn(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    user, view = whose_turn(authenticated_event)
    other = BOB if user == ALICE else ALICE

    status, _ = act(authenticated_event, other, {"battleId": battle_id, "type": "auto"})
    assert status == 409

    strike = next(a for a in view["actions"] if a["id"] == "strike")
    status, body = act(authenticated_event, user, {
        "battleId": battle_id, "type": "skill", "skill": "strike",
        "target": strike["targets"][0], "since": view["seq"],
    })
    assert status == 200, body
    damage = [e for e in body["events"] if e["type"] == "damage"]
    # O alvo escolhido (visto como "e") é uma carta do adversário.
    assert damage and damage[0]["target"] == strike["targets"][0]
    assert body["battle"]["seq"] == view["seq"] + 1

    # O outro jogador recebe os mesmos eventos, do ponto de vista dele.
    _, theirs = current(authenticated_event, other, since=view["seq"])
    assert [e["type"] for e in theirs["events"]] == [e["type"] for e in body["events"]]
    their_damage = next(e for e in theirs["events"] if e["type"] == "damage")
    # O alvo é a carta do outro jogador: para ele, uma carta do próprio time.
    assert their_damage["target"] == battle.view_id(damage[0]["target"], "enemy")
    assert their_damage["target"].startswith("p")


def test_action_rejects_invalid_requests(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    user, _ = whose_turn(authenticated_event)
    for body in (
        {"battleId": battle_id, "type": "dance"},
        {"type": "auto"},
        {"battleId": battle_id, "type": "skill", "skill": None},
    ):
        assert act(authenticated_event, user, body)[0] == 400
    assert act(authenticated_event, user, {"battleId": "other", "type": "auto"})[0] == 404
    status, body = act(authenticated_event, user, {
        "battleId": battle_id, "type": "skill", "skill": "cataclysm", "target": None,
    })
    assert status == 400


def test_forfeit_finishes_for_both_with_rewards(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    status, body = act(authenticated_event, BOB, {"battleId": battle_id, "type": "forfeit"})
    assert status == 200
    assert body["result"]["outcome"] == "lost"
    assert body["result"]["reason"] == "forfeit"
    assert body["result"]["experienceGained"] == 0

    _, alice = current(authenticated_event, ALICE)
    assert alice["battle"]["status"] == "won"
    assert alice["result"]["outcome"] == "won"
    assert alice["result"]["reason"] == "opponent_forfeit"
    assert alice["result"]["experienceGained"] == battle.PVP["experience"]

    progress = db.tables["progress"]
    assert progress[(ALICE, None)]["experience"]["N"] == str(battle.PVP["experience"])
    assert progress[(ALICE, None)]["wins"]["N"] == "1"
    assert progress[(BOB, None)]["losses"]["N"] == "1"
    assert {p["status"]["S"] for p in db.tables["players"].values()} == {"finished"}

    # Acabou: os dois podem desafiar de novo.
    _, lobby_body = lobby(authenticated_event, ALICE)
    assert lobby_body["battle"] is None
    assert challenge(authenticated_event, ALICE, "bob", ALICE_TEAM)[0] == 201
    assert act(authenticated_event, ALICE, {"battleId": battle_id, "type": "auto"})[0] == 409


def test_level_up_in_duel_pays_shards(authenticated_event, db, monkeypatch):
    monkeypatch.setattr(battle, "PVP", {**battle.PVP, "experience": 1000})
    battle_id = start_duel(authenticated_event)
    act(authenticated_event, BOB, {"battleId": battle_id, "type": "forfeit"})
    _, alice = current(authenticated_event, ALICE)
    assert alice["result"]["leveledUp"]
    assert int(db.tables["wallet"][(ALICE, None)]["balance"]["N"]) == alice["result"]["shardsReward"]
    assert (BOB, None) not in db.tables["wallet"]


def test_finish_retries_when_progress_changes(authenticated_event, db, monkeypatch):
    battle_id = start_duel(authenticated_event)
    original = pvp_battle.get_progress
    calls = {"count": 0}

    def racing_progress(user_id):
        calls["count"] += 1
        if calls["count"] == 1:
            # Outra batalha da Alice termina entre a leitura e a gravação.
            db.tables["progress"][(ALICE, None)] = {
                "userId": {"S": ALICE}, "experience": {"N": "10"},
            }
            return 0, 0, 0, False
        return original(user_id)

    monkeypatch.setattr(pvp_battle, "get_progress", racing_progress)
    status, _ = act(authenticated_event, BOB, {"battleId": battle_id, "type": "forfeit"})
    assert status == 200
    assert db.tables["progress"][(ALICE, None)]["experience"]["N"] == str(
        10 + battle.PVP["experience"]
    )


def test_expired_turn_is_played_on_next_poll(authenticated_event, db, clock):
    battle_id = start_duel(authenticated_event)
    user, view = whose_turn(authenticated_event)
    other = BOB if user == ALICE else ALICE

    clock["value"] += pvp.TURN_SECONDS
    _, body = current(authenticated_event, other, since=view["seq"])
    assert body["events"][0]["type"] == "timeout"
    state = stored_state(db, battle_id)
    side = "player" if user == ALICE else "enemy"
    assert state["missed"][side] == 1



def test_late_action_is_rejected_after_timeout(authenticated_event, db, clock):
    battle_id = start_duel(authenticated_event)
    user, view = whose_turn(authenticated_event)
    clock["value"] += pvp.TURN_SECONDS
    status, body = act(authenticated_event, user, {"battleId": battle_id, "type": "auto"})
    assert status == 409
    assert "Time ran out" in body["message"]
    assert stored_state(db, battle_id)["seq"] == view["seq"] + 1


def test_concurrent_change_is_detected(authenticated_event, db, monkeypatch):
    battle_id = start_duel(authenticated_event)
    user, _ = whose_turn(authenticated_event)
    original = pvp_battle.load_duel

    def stale_load(user_id, battle_id=None):
        duel = original(user_id, battle_id)
        item = db.tables["battles"][(battle_id, None)]
        item["version"] = {"N": str(int(item["version"]["N"]) + 1)}
        return duel

    monkeypatch.setattr(pvp_battle, "load_duel", stale_load)
    status, _ = act(authenticated_event, user, {"battleId": battle_id, "type": "auto"})
    assert status == 409


def test_full_duel_with_auto_actions(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    for _ in range(400):
        _, alice = current(authenticated_event, ALICE)
        if alice["battle"]["status"] != "active":
            break
        user = ALICE if alice["battle"]["yourTurn"] else BOB
        status, body = act(authenticated_event, user, {"battleId": battle_id, "type": "auto"})
        assert status == 200, body
    _, alice = current(authenticated_event, ALICE)
    _, bob = current(authenticated_event, BOB)
    outcomes = {alice["result"]["outcome"], bob["result"]["outcome"]}
    assert outcomes in ({"won", "lost"}, {"draw"})
    # Cada um vê o motivo do próprio ponto de vista.
    for body in (alice, bob):
        expected = {"won": "victory", "lost": "defeat", "draw": "timeout"}[body["result"]["outcome"]]
        assert body["result"]["reason"] == expected
        assert body["battle"]["endReason"] == expected
        end = [e for e in current(authenticated_event, ALICE if body is alice else BOB, since=0)[1]["events"] if e["type"] == "end"]
        assert not end or end[0]["reason"] == expected
    assert alice["result"]["experienceGained"] > 0
    assert bob["result"]["experienceGained"] > 0


def test_current_by_battle_id_skips_the_pointer(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    db.calls.clear()
    status, body = current(authenticated_event, BOB, since=0, battle_id=battle_id)
    assert status == 200
    assert body["battle"]["battleId"] == battle_id
    assert sorted(u["fileName"] for u in body["battle"]["units"] if u["side"] == "player") == sorted(BOB_TEAM)
    assert [table for op, table in db.calls if op == "get_item"] == ["battles"]


def test_current_by_battle_id_only_for_its_players(authenticated_event, db):
    battle_id = start_duel(authenticated_event)
    assert current(authenticated_event, CAROL, battle_id=battle_id)[0] == 404
    assert current(authenticated_event, ALICE, battle_id="missing")[0] == 404
    status, _ = act(authenticated_event, CAROL, {"battleId": battle_id, "type": "forfeit"})
    assert status == 404


def test_current_unchanged_is_a_short_answer(authenticated_event, db, clock):
    battle_id = start_duel(authenticated_event)
    _, full = current(authenticated_event, ALICE, battle_id=battle_id)
    seq = full["battle"]["seq"]
    clock["value"] += 10
    status, body = current(authenticated_event, ALICE, since=seq, battle_id=battle_id)
    assert status == 200
    assert body == {
        "unchanged": True,
        "battle": {
            "battleId": battle_id,
            "seq": seq,
            "status": "active",
            "turnSecondsLeft": pvp.TURN_SECONDS - 10,
        },
    }
    # Quando a vez esgota, a resposta volta completa com os eventos novos.
    clock["value"] += pvp.TURN_SECONDS
    _, body = current(authenticated_event, ALICE, since=seq, battle_id=battle_id)
    assert "unchanged" not in body
    assert body["battle"]["seq"] == seq + 1
    assert body["events"][0]["type"] == "timeout"
