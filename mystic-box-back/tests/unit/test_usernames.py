import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mystic_shared import usernames

from get_profile import app as get_profile
from search_users import app as search_users
from set_username import app as set_username

NOW = 1_800_000_000
DAY = 24 * 60 * 60


def transaction_conflict(*failed_indexes, size=2):
    return ClientError(
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [
                {"Code": "ConditionalCheckFailed" if i in failed_indexes else "None"}
                for i in range(size)
            ],
        },
        "TransactWriteItems",
    )


def profile_item(username, changed_at):
    return {
        "Item": {
            "userId": {"S": "user-123"},
            "username": {"S": username},
            "usernameLower": {"S": username.lower()},
            "usernameChangedAt": {"N": str(changed_at)},
        }
    }


# ---------- regras ----------


@pytest.mark.parametrize("value", ["Ana", "mage_42", "A" * 20, "  Lyra  "])
def test_validate_username_accepts(value):
    username, error = usernames.validate_username(value)
    assert error is None
    assert username == value.strip()


@pytest.mark.parametrize(
    "value", [None, 123, "", "ab", "A" * 21, "1abc", "_abc", "has space", "ção", "a-b"]
)
def test_validate_username_rejects(value):
    username, error = usernames.validate_username(value)
    assert username is None
    assert error


def test_change_status_without_previous_change():
    assert usernames.change_status(None, NOW) == {
        "canChange": True,
        "retryAfterSeconds": 0,
        "nextChangeAt": None,
    }


def test_change_status_waits_thirty_days():
    status = usernames.change_status(NOW - 10 * DAY, NOW)
    assert status["canChange"] is False
    assert status["retryAfterSeconds"] == 20 * DAY
    assert status["nextChangeAt"] == NOW + 20 * DAY

    assert usernames.change_status(NOW - 30 * DAY, NOW)["canChange"] is True


@pytest.mark.parametrize("value,expected", [("Ly", "ly"), (" MaGe ", "mage"), ("a", None), ("a b", None), (None, None)])
def test_normalize_search(value, expected):
    assert usernames.normalize_search(value) == expected


# ---------- set_username ----------


@pytest.fixture()
def username_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(set_username, "_client", client)
    monkeypatch.setattr(set_username, "USER_PROFILES_TABLE", "profiles")
    monkeypatch.setattr(set_username, "USERNAMES_TABLE", "usernames")
    monkeypatch.setattr(set_username.time, "time", lambda: NOW)
    client.get_item.return_value = {}
    return client


def post_username(authenticated_event, username, **extra):
    body = json.dumps({"username": username, **extra})
    return set_username.lambda_handler(authenticated_event(httpMethod="POST", body=body), "")


def test_set_username_requires_authentication(apigw_event):
    ret = set_username.lambda_handler(dict(apigw_event, httpMethod="POST"), "")
    assert ret["statusCode"] == 401


def test_set_username_rejects_invalid(authenticated_event, username_client):
    ret = post_username(authenticated_event, "a b")
    assert ret["statusCode"] == 400
    username_client.transact_write_items.assert_not_called()


def test_set_username_first_time(authenticated_event, username_client):
    ret = post_username(authenticated_event, "Lyra_01")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["username"] == "Lyra_01"
    assert data["usernameChange"]["canChange"] is False
    assert data["usernameChange"]["retryAfterSeconds"] == 30 * DAY

    items = username_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 2
    update = items[0]["Update"]
    assert update["Key"] == {"userId": {"S": "user-123"}}
    assert update["ConditionExpression"] == "attribute_not_exists(usernameLower)"
    assert update["ExpressionAttributeValues"][":lower"] == {"S": "lyra_01"}
    assert update["ExpressionAttributeValues"][":now"] == {"N": str(NOW)}
    reservation = items[1]["Put"]
    assert reservation["Item"] == {
        "usernameLower": {"S": "lyra_01"},
        "userId": {"S": "user-123"},
    }


def test_set_username_ignores_extra_fields(authenticated_event, username_client):
    post_username(authenticated_event, "Lyra", usernameChangedAt=0, userId="other")

    items = username_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert items[0]["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert items[0]["Update"]["ExpressionAttributeValues"][":now"] == {"N": str(NOW)}


def test_set_username_on_cooldown(authenticated_event, username_client):
    username_client.get_item.return_value = profile_item("Lyra", NOW - 5 * DAY)

    ret = post_username(authenticated_event, "Astra")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 429
    assert data["retryAfterSeconds"] == 25 * DAY
    username_client.transact_write_items.assert_not_called()


def test_set_username_after_cooldown_releases_old_name(authenticated_event, username_client):
    username_client.get_item.return_value = profile_item("Lyra", NOW - 31 * DAY)

    ret = post_username(authenticated_event, "Astra")

    assert ret["statusCode"] == 200
    items = username_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 3
    values = items[0]["Update"]["ExpressionAttributeValues"]
    assert values[":oldLower"] == {"S": "lyra"}
    assert values[":cutoff"] == {"N": str(NOW - 30 * DAY)}
    assert items[2]["Delete"]["Key"] == {"usernameLower": {"S": "lyra"}}
    assert items[2]["Delete"]["ConditionExpression"] == "userId = :me"


def test_set_username_case_change_keeps_reservation(authenticated_event, username_client):
    username_client.get_item.return_value = profile_item("lyra", NOW - 31 * DAY)

    ret = post_username(authenticated_event, "Lyra")

    assert ret["statusCode"] == 200
    items = username_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 2


def test_set_username_same_name(authenticated_event, username_client):
    username_client.get_item.return_value = profile_item("Lyra", NOW - 31 * DAY)

    ret = post_username(authenticated_event, "Lyra")
    assert ret["statusCode"] == 400


def test_set_username_taken(authenticated_event, username_client):
    username_client.transact_write_items.side_effect = transaction_conflict(1)

    ret = post_username(authenticated_event, "Lyra")
    assert ret["statusCode"] == 409
    assert "taken" in json.loads(ret["body"])["message"]


def test_set_username_concurrent_change(authenticated_event, username_client):
    username_client.transact_write_items.side_effect = transaction_conflict(0)

    ret = post_username(authenticated_event, "Lyra")
    assert ret["statusCode"] == 409


# ---------- get_profile ----------


@pytest.fixture()
def profile_client(monkeypatch):
    client = MagicMock()
    # Ascensões (títulos dos capítulos secretos): nenhuma.
    client.query.return_value = {"Items": []}
    monkeypatch.setattr(get_profile, "_client", client)
    monkeypatch.setattr(get_profile, "USER_PROGRESS_TABLE", "progress")
    monkeypatch.setattr(get_profile, "USER_PROFILES_TABLE", "profiles")
    monkeypatch.setattr(get_profile.time, "time", lambda: NOW)
    return client


def test_get_profile_without_username(authenticated_event, profile_client):
    profile_client.get_item.return_value = {}

    data = json.loads(get_profile.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"])

    assert data["userId"] == "user-123"
    assert data["username"] is None
    assert data["usernameChange"]["canChange"] is True
    assert data["usernameRules"]["changeCooldownDays"] == 30


def test_get_profile_with_username(authenticated_event, profile_client):
    def get_item(TableName, **kwargs):
        return profile_item("Lyra", NOW - DAY) if TableName == "profiles" else {}

    profile_client.get_item.side_effect = get_item

    data = json.loads(get_profile.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"])

    assert data["username"] == "Lyra"
    assert data["level"] == 1
    assert data["usernameChange"]["canChange"] is False
    assert data["usernameChange"]["retryAfterSeconds"] == 29 * DAY


# ---------- search_users ----------


@pytest.fixture()
def search_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(search_users, "_client", client)
    monkeypatch.setattr(search_users, "USER_PROFILES_TABLE", "profiles")
    monkeypatch.setattr(search_users, "USER_PROGRESS_TABLE", "progress")
    client.query.return_value = {
        "Items": [
            {"userId": {"S": "user-123"}, "username": {"S": "Lyra"}},
            {"userId": {"S": "user-456"}, "username": {"S": "Lyrandor"}},
        ]
    }
    client.batch_get_item.return_value = {
        "Responses": {
            "progress": [{"userId": {"S": "user-456"}, "experience": {"N": "230"}}],
            "profiles": [{"userId": {"S": "user-456"}, "title": {"S": "summoner"}}],
        }
    }
    return client


def search(authenticated_event, query):
    event = authenticated_event(httpMethod="GET", queryStringParameters={"q": query})
    return search_users.lambda_handler(event, "")


def test_search_requires_authentication(apigw_event):
    ret = search_users.lambda_handler(dict(apigw_event, httpMethod="GET"), "")
    assert ret["statusCode"] == 401


@pytest.mark.parametrize("query", ["", "a", "a b", "x" * 21])
def test_search_rejects_bad_query(authenticated_event, search_client, query):
    assert search(authenticated_event, query)["statusCode"] == 400
    search_client.query.assert_not_called()


def test_search_by_prefix(authenticated_event, search_client):
    ret = search(authenticated_event, "LYR")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["players"] == [
        {"username": "Lyra", "level": 1, "title": None, "isYou": True},
        {"username": "Lyrandor", "level": 3, "title": "Summoner", "isYou": False},
    ]
    kwargs = search_client.query.call_args.kwargs
    assert kwargs["IndexName"] == "UsernameSearchIndex"
    assert kwargs["ExpressionAttributeValues"][":query"] == {"S": "lyr"}
    assert kwargs["Limit"] == usernames.SEARCH_MAX_RESULTS
    # O id do Cognito dos outros jogadores não é exposto.
    assert "userId" not in data["players"][1]


def test_search_without_results(authenticated_event, search_client):
    search_client.query.return_value = {"Items": []}

    data = json.loads(search(authenticated_event, "zz")["body"])

    assert data["players"] == []
    search_client.batch_get_item.assert_not_called()
