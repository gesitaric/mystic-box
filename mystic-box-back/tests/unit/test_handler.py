import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from get_summon_status import app as get_summon_status
from get_user_cards import app as get_user_cards
from open_box import app as open_box
from save_user_card import app as save_user_card


def test_open_box_options(apigw_event):
    ret = open_box.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_user_cards_options(apigw_event):
    ret = get_user_cards.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_user_cards_requires_authentication(apigw_event):
    ret = get_user_cards.lambda_handler(apigw_event, "")

    assert ret["statusCode"] == 401


def test_get_user_cards_returns_cards(authenticated_event, monkeypatch):
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {
                "userId": "user-123",
                "ownedCardId": "owned-1",
                "name": "Astra",
                "rarity": 5,
                "file_name": "astra.jfif",
                "obtainedAt": "2026-01-01T00:00:00+00:00",
            }
        ]
    }
    monkeypatch.setattr(get_user_cards, "_table", table)

    ret = get_user_cards.lambda_handler(authenticated_event(), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["cards"][0]["ownedCardId"] == "owned-1"
    assert data["cards"][0]["name"] == "Astra"
    # Preço de venda vem das definições do servidor.
    assert data["cards"][0]["sellPrice"] == 250
    table.query.assert_called_once()


@pytest.fixture()
def cards_table(monkeypatch):
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {"ownedCardId": "1", "name": "Bruma", "rarity": 3, "obtainedAt": "2026-01-03"},
            {"ownedCardId": "2", "name": "Ágata", "rarity": 5, "obtainedAt": "2026-01-01"},
            {"ownedCardId": "3", "name": "astra", "rarity": 3, "obtainedAt": "2026-01-02"},
            {"ownedCardId": "4", "name": "Astra", "rarity": 1, "obtainedAt": "2026-01-04"},
        ]
    }
    monkeypatch.setattr(get_user_cards, "_table", table)
    return table


def get_card_ids(authenticated_event, **query):
    ret = get_user_cards.lambda_handler(
        authenticated_event(queryStringParameters=query or None), ""
    )
    assert ret["statusCode"] == 200
    return [card["ownedCardId"] for card in json.loads(ret["body"])["cards"]]


def test_get_user_cards_default_sort_is_obtained_at_desc(authenticated_event, cards_table):
    assert get_card_ids(authenticated_event) == ["4", "1", "3", "2"]


@pytest.mark.parametrize(
    "query, expected",
    [
        ({"sort": "rarity", "order": "desc"}, ["2", "3", "1", "4"]),
        ({"sort": "rarity", "order": "asc"}, ["4", "3", "1", "2"]),
        ({"sort": "rarity"}, ["2", "3", "1", "4"]),
        ({"sort": "name", "order": "asc"}, ["2", "4", "3", "1"]),
        ({"sort": "name", "order": "desc"}, ["1", "4", "3", "2"]),
        ({"sort": "obtainedAt", "order": "asc"}, ["2", "3", "1", "4"]),
    ],
)
def test_get_user_cards_sorts(authenticated_event, cards_table, query, expected):
    assert get_card_ids(authenticated_event, **query) == expected


@pytest.mark.parametrize(
    "query",
    [{"sort": "power"}, {"order": "up"}, {"sort": "name", "order": "ASC"}],
)
def test_get_user_cards_rejects_invalid_sort(authenticated_event, cards_table, query):
    ret = get_user_cards.lambda_handler(
        authenticated_event(queryStringParameters=query), ""
    )

    assert ret["statusCode"] == 400
    cards_table.query.assert_not_called()


def test_get_user_cards_handles_dynamodb_error(authenticated_event, monkeypatch):
    table = MagicMock()
    table.query.side_effect = ClientError({"Error": {"Code": "500"}}, "Query")
    monkeypatch.setattr(get_user_cards, "_table", table)

    ret = get_user_cards.lambda_handler(authenticated_event(), "")

    assert ret["statusCode"] == 500


def test_save_user_card_options(apigw_event):
    ret = save_user_card.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_save_user_card_requires_authentication(apigw_event):
    ret = save_user_card.lambda_handler(apigw_event, "")

    assert ret["statusCode"] == 401


@pytest.fixture()
def status_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(get_summon_status, "_client", client)
    monkeypatch.setattr(get_summon_status, "USER_SUMMON_STATE_TABLE", "summon-state")
    monkeypatch.setattr(get_summon_status, "SUMMON_COOLDOWN_SECONDS", 3600)
    monkeypatch.setattr(get_summon_status.time, "time", lambda: 10_000)
    return client


def test_get_summon_status_options(apigw_event):
    ret = get_summon_status.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_summon_status_requires_authentication(apigw_event):
    ret = get_summon_status.lambda_handler(apigw_event, "")

    assert ret["statusCode"] == 401


def test_get_summon_status_without_previous_summon(authenticated_event, status_client):
    status_client.get_item.return_value = {}

    ret = get_summon_status.lambda_handler(authenticated_event(), "")

    assert ret["statusCode"] == 200
    assert json.loads(ret["body"]) == {"retryAfterSeconds": 0, "cooldownSeconds": 3600}


def test_get_summon_status_during_cooldown(authenticated_event, status_client):
    status_client.get_item.return_value = {"Item": {"lastSummonAt": {"N": "9000"}}}

    ret = get_summon_status.lambda_handler(authenticated_event(), "")

    assert json.loads(ret["body"])["retryAfterSeconds"] == 2600


def test_get_summon_status_after_cooldown(authenticated_event, status_client):
    status_client.get_item.return_value = {"Item": {"lastSummonAt": {"N": "1000"}}}

    ret = get_summon_status.lambda_handler(authenticated_event(), "")

    assert json.loads(ret["body"])["retryAfterSeconds"] == 0


def test_get_summon_status_handles_dynamodb_error(authenticated_event, status_client):
    status_client.get_item.side_effect = ClientError({"Error": {"Code": "500"}}, "GetItem")

    ret = get_summon_status.lambda_handler(authenticated_event(), "")

    assert ret["statusCode"] == 500
