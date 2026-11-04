import json
import random

import pytest
from botocore.exceptions import ClientError
from mystic_shared import battle, progression

from get_battle import app as get_battle
from play_battle import app as play_battle

USER = "user-123"
TEAM = ["rowan.jfif", "brina.jfif", "maelis.jfif"]


class FakeDynamo:
    """DynamoDB mínimo em memória para os testes das batalhas."""

    def __init__(self):
        self.tables = {"battles": {}, "cards": [], "progress": {}, "wallet": {}}
        self.fail_progress_condition = 0

    # --- leitura
    def get_item(self, TableName, Key, **_):
        item = self.tables[TableName].get(Key["userId"]["S"])
        return {"Item": json.loads(json.dumps(item))} if item else {}

    def query(self, TableName, ExpressionAttributeValues, **_):
        user_id = ExpressionAttributeValues[":userId"]["S"]
        items = [
            {"file_name": {"S": card["file_name"]}}
            for card in self.tables[TableName]
            if card["userId"] == user_id
        ]
        return {"Items": items}

    # --- escrita
    def _check_version(self, put):
        if "ConditionExpression" not in put:
            return True
        current = self.tables["battles"].get(put["Item"]["userId"]["S"])
        expected = put["ExpressionAttributeValues"][":expected"]["N"]
        return current is not None and current["version"]["N"] == expected

    def put_item(self, **put):
        if not self._check_version(put):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
            )
        self.tables[put["TableName"]][put["Item"]["userId"]["S"]] = put["Item"]

    def transact_write_items(self, TransactItems):
        reasons = []
        for item in TransactItems:
            ok = True
            if "Put" in item:
                ok = self._check_version(item["Put"])
            elif item["Update"]["TableName"] == "progress":
                if self.fail_progress_condition:
                    self.fail_progress_condition -= 1
                    ok = False
            reasons.append({"Code": "None" if ok else "ConditionalCheckFailed"})
        if any(r["Code"] != "None" for r in reasons):
            raise ClientError(
                {"Error": {"Code": "TransactionCanceledException"},
                 "CancellationReasons": reasons},
                "TransactWriteItems",
            )

        for item in TransactItems:
            if "Put" in item:
                self.put_item(**{k: v for k, v in item["Put"].items()
                                 if k == "TableName" or k == "Item"})
                continue
            update = item["Update"]
            values = update["ExpressionAttributeValues"]
            user_id = update["Key"]["userId"]["S"]
            row = self.tables[update["TableName"]].setdefault(
                user_id, {"userId": {"S": user_id}}
            )
            if update["TableName"] == "progress":
                row["experience"] = values[":new"]
                for field in ("wins", "losses"):
                    old = int(row.get(field, {"N": "0"})["N"])
                    row[field] = {"N": str(old + int(values[f":{field}"]["N"]))}
            else:
                old = int(row.get("balance", {"N": "0"})["N"])
                row["balance"] = {"N": str(old + int(values[":shards"]["N"]))}


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo()
    fake.tables["cards"] = [{"userId": USER, "file_name": name} for name in TEAM]
    for module in (play_battle, get_battle):
        monkeypatch.setattr(module, "_client", fake)
        monkeypatch.setattr(module, "BATTLES_TABLE", "battles")
        monkeypatch.setattr(module, "USER_PROGRESS_TABLE", "progress")
    monkeypatch.setattr(play_battle, "USER_CARDS_TABLE", "cards")
    monkeypatch.setattr(play_battle, "USER_WALLET_TABLE", "wallet")
    monkeypatch.setattr(play_battle, "new_rng", lambda: random.Random(42))
    return fake


def start_event(authenticated_event, body):
    return authenticated_event(
        httpMethod="POST", resource="/battles", body=json.dumps(body)
    )


def action_event(authenticated_event, body):
    return authenticated_event(
        httpMethod="POST", resource="/battles/current/actions", body=json.dumps(body)
    )


def call(handler, event):
    ret = handler.lambda_handler(event, "")
    return ret["statusCode"], json.loads(ret["body"])


def start(authenticated_event, difficulty="novice", team=TEAM):
    return call(
        play_battle,
        start_event(authenticated_event, {"team": team, "difficulty": difficulty}),
    )


def stored_state(db):
    return json.loads(db.tables["battles"][USER]["state"]["S"])


# ---------- começar ----------


def test_play_battle_options(apigw_event):
    ret = play_battle.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")
    assert ret["statusCode"] == 200


def test_play_battle_requires_authentication(apigw_event):
    ret = play_battle.lambda_handler(
        dict(apigw_event, httpMethod="POST", resource="/battles"), ""
    )
    assert ret["statusCode"] == 401


def test_start_battle(authenticated_event, db):
    status, data = start(authenticated_event)

    assert status == 201
    view = data["battle"]
    assert view["status"] == "active"
    assert [u["fileName"] for u in view["units"] if u["side"] == "player"] == TEAM
    assert view["turn"].startswith("p")
    assert data["events"] and data["result"] is None
    assert db.tables["battles"][USER]["version"]["N"] == "1"
    assert stored_state(db)["battleId"] == view["battleId"]


def test_start_battle_ignores_client_stats(authenticated_event, db):
    body = {"team": TEAM, "difficulty": "novice", "stats": {"might": 9999}}
    status, data = call(play_battle, start_event(authenticated_event, body))

    assert status == 201
    for unit in data["battle"]["units"]:
        assert unit["stats"]["might"] < 9999


@pytest.mark.parametrize(
    "body",
    [
        {"team": TEAM[:2], "difficulty": "novice"},
        {"team": "rowan.jfif", "difficulty": "novice"},
        {"team": [1, 2, 3], "difficulty": "novice"},
        {"team": TEAM},
        {"team": [TEAM[0], TEAM[0], TEAM[1]], "difficulty": "novice"},
        {"team": TEAM, "difficulty": "impossible"},
        {"team": ["nope.jfif", TEAM[1], TEAM[2]], "difficulty": "novice"},
    ],
)
def test_start_battle_rejects_invalid_requests(authenticated_event, db, body):
    status, _ = call(play_battle, start_event(authenticated_event, body))
    assert status == 400


def test_start_battle_requires_owned_cards(authenticated_event, db):
    status, data = start(authenticated_event, team=["astra.jfif", TEAM[1], TEAM[2]])

    assert status == 409
    assert "Astra" in data["message"]


def test_start_battle_locked_difficulty(authenticated_event, db):
    status, data = start(authenticated_event, difficulty="master")

    assert status == 400
    assert "level" in data["message"]


def test_start_battle_uses_player_level(authenticated_event, db):
    db.tables["progress"][USER] = {"userId": {"S": USER}, "experience": {"N": "230"}}

    status, data = start(authenticated_event, difficulty="adept")

    assert status == 201
    assert {u["level"] for u in data["battle"]["units"] if u["side"] == "player"} == {3}


# ---------- jogar ----------


def test_play_turn(authenticated_event, db):
    _, data = start(authenticated_event)
    battle_id = data["battle"]["battleId"]
    target = data["battle"]["actions"][0]["targets"][0]

    status, data = call(
        play_battle,
        action_event(authenticated_event, {
            "battleId": battle_id, "type": "skill", "skill": "strike", "target": target,
        }),
    )

    assert status == 200
    assert data["events"][0]["type"] == "skill"
    assert data["events"][0]["skill"] == "strike"
    assert db.tables["battles"][USER]["version"]["N"] == "2"


def test_play_turn_wrong_battle(authenticated_event, db):
    start(authenticated_event)
    status, _ = call(
        play_battle,
        action_event(authenticated_event, {"battleId": "other", "type": "auto"}),
    )
    assert status == 404


def test_play_turn_without_battle(authenticated_event, db):
    status, _ = call(
        play_battle,
        action_event(authenticated_event, {"battleId": "x", "type": "auto"}),
    )
    assert status == 404


@pytest.mark.parametrize(
    "body",
    [
        {"type": "auto"},
        {"battleId": "b", "type": "dance"},
        {"battleId": "b", "type": "skill"},
        {"battleId": "b", "type": "skill", "skill": "strike", "target": 5},
    ],
)
def test_play_turn_rejects_invalid_requests(authenticated_event, db, body):
    status, _ = call(play_battle, action_event(authenticated_event, body))
    assert status == 400


def test_play_turn_invalid_skill(authenticated_event, db):
    _, data = start(authenticated_event)
    status, data = call(
        play_battle,
        action_event(authenticated_event, {
            "battleId": data["battle"]["battleId"], "type": "skill", "skill": "cataclysm",
        }),
    )
    assert status == 400


def test_play_turn_concurrent_change(authenticated_event, db, monkeypatch):
    _, data = start(authenticated_event)
    battle_id = data["battle"]["battleId"]
    original_get = db.get_item

    def stale_get(TableName, Key, **kwargs):
        item = original_get(TableName, Key, **kwargs)
        # Outra aba já jogou o turno depois desta leitura.
        db.tables["battles"][USER]["version"] = {"N": "7"}
        return item

    monkeypatch.setattr(db, "get_item", stale_get)
    status, _ = call(
        play_battle, action_event(authenticated_event, {"battleId": battle_id, "type": "auto"})
    )
    assert status == 409


def play_until_end(authenticated_event, battle_id):
    for _ in range(500):
        status, data = call(
            play_battle,
            action_event(authenticated_event, {"battleId": battle_id, "type": "auto"}),
        )
        assert status == 200
        if data["result"]:
            return data
    raise AssertionError("Battle never ended")


def test_finished_battle_grants_experience(authenticated_event, db):
    _, data = start(authenticated_event)
    data = play_until_end(authenticated_event, data["battle"]["battleId"])
    result = data["result"]

    assert data["battle"]["status"] in ("won", "lost")
    assert result["outcome"] == data["battle"]["status"]
    assert result["experienceGained"] > 0
    stored = db.tables["progress"][USER]
    assert int(stored["experience"]["N"]) == result["experienceGained"]
    if result["outcome"] == "won":
        assert stored["wins"]["N"] == "1" and stored["losses"]["N"] == "0"
        assert result["experienceGained"] == battle.DIFFICULTIES["novice"]["experience"]
    else:
        assert stored["losses"]["N"] == "1"
        assert result["experienceGained"] < battle.DIFFICULTIES["novice"]["experience"]

    # Batalha terminada não aceita mais ações.
    status, _ = call(
        play_battle,
        action_event(authenticated_event, {"battleId": data["battle"]["battleId"],
                                           "type": "auto"}),
    )
    assert status == 409


def test_forfeit_counts_as_loss_without_experience(authenticated_event, db):
    _, data = start(authenticated_event)
    status, data = call(
        play_battle,
        action_event(authenticated_event, {"battleId": data["battle"]["battleId"],
                                           "type": "forfeit"}),
    )

    assert status == 200
    assert data["result"]["outcome"] == "lost"
    assert data["result"]["experienceGained"] == 0
    assert db.tables["progress"][USER]["losses"]["N"] == "1"


def test_level_up_pays_shards(authenticated_event, db, monkeypatch):
    db.tables["progress"][USER] = {"userId": {"S": USER}, "experience": {"N": "95"}}
    monkeypatch.setattr(play_battle, "battle_experience", lambda state: 40)
    _, data = start(authenticated_event)

    _, data = call(
        play_battle,
        action_event(authenticated_event, {"battleId": data["battle"]["battleId"],
                                           "type": "forfeit"}),
    )
    result = data["result"]

    assert result["leveledUp"] is True
    assert result["previousLevel"] == 1 and result["level"] == 2
    assert result["shardsReward"] == progression.level_up_reward(1, 2)
    assert db.tables["wallet"][USER]["balance"]["N"] == str(result["shardsReward"])


def test_finish_retries_when_progress_changes(authenticated_event, db):
    _, data = start(authenticated_event)
    db.fail_progress_condition = 1

    status, data = call(
        play_battle,
        action_event(authenticated_event, {"battleId": data["battle"]["battleId"],
                                           "type": "forfeit"}),
    )

    assert status == 200
    assert db.tables["progress"][USER]["losses"]["N"] == "1"


# ---------- get_battle ----------


def test_get_battle_requires_authentication(apigw_event):
    ret = get_battle.lambda_handler(dict(apigw_event, httpMethod="GET"), "")
    assert ret["statusCode"] == 401


def test_get_battle_without_battle(authenticated_event, db):
    status, data = call(get_battle, authenticated_event(httpMethod="GET"))

    assert status == 200
    assert data["battle"] is None
    assert data["teamSize"] == battle.TEAM_SIZE
    assert data["progress"]["level"] == 1
    unlocked = [d["id"] for d in data["difficulties"] if d["unlocked"]]
    assert unlocked == ["novice"]


def test_get_battle_returns_active_battle(authenticated_event, db):
    _, started = start(authenticated_event)

    status, data = call(get_battle, authenticated_event(httpMethod="GET"))

    assert status == 200
    assert data["battle"]["battleId"] == started["battle"]["battleId"]


def test_get_battle_hides_finished_battle(authenticated_event, db):
    _, started = start(authenticated_event)
    call(
        play_battle,
        action_event(authenticated_event, {"battleId": started["battle"]["battleId"],
                                           "type": "forfeit"}),
    )

    _, data = call(get_battle, authenticated_event(httpMethod="GET"))

    assert data["battle"] is None
    assert data["progress"]["losses"] == 1
