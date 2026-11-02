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


def test_get_user_cards_groups_repeated_cards(authenticated_event, monkeypatch):
    def owned(owned_id, file_name, name, rarity, obtained_at):
        return {
            "userId": "user-123",
            "ownedCardId": owned_id,
            "name": name,
            "rarity": rarity,
            "file_name": file_name,
            "obtainedAt": obtained_at,
        }

    table = MagicMock()
    table.query.return_value = {
        "Items": [
            owned("a1", "astra.jfif", "Astra", 5, "2026-01-02T00:00:00+00:00"),
            owned("a2", "astra.jfif", "Astra", 5, "2026-01-01T00:00:00+00:00"),
            owned("a3", "astra.jfif", "Astra", 5, "2026-01-03T00:00:00+00:00"),
            owned("r1", "rowan.jfif", "Rowan", 3, "2026-01-01T00:00:00+00:00"),
        ]
    }
    monkeypatch.setattr(get_user_cards, "_table", table)

    ret = get_user_cards.lambda_handler(authenticated_event(), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["totalCards"] == 4
    assert data["cards"] == [
        {
            "file_name": "astra.jfif",
            "name": "Astra",
            "rarity": 5,
            "quantity": 3,
            "firstObtainedAt": "2026-01-01T00:00:00+00:00",
            "lastObtainedAt": "2026-01-03T00:00:00+00:00",
            # Preço de venda vem das definições do servidor.
            "sellPrice": 250,
            "maxSellQuantity": 3,
        },
        {
            "file_name": "rowan.jfif",
            "name": "Rowan",
            "rarity": 3,
            "quantity": 1,
            "firstObtainedAt": "2026-01-01T00:00:00+00:00",
            "lastObtainedAt": "2026-01-01T00:00:00+00:00",
            "sellPrice": 10,
            "maxSellQuantity": 1,
        },
    ]
    table.query.assert_called_once()


def test_get_user_cards_unknown_card_cannot_be_sold(authenticated_event, monkeypatch):
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {"ownedCardId": "1", "name": "Antiga", "rarity": 3, "file_name": "antiga.jfif"}
        ]
    }
    monkeypatch.setattr(get_user_cards, "_table", table)

    data = json.loads(get_user_cards.lambda_handler(authenticated_event(), "")["body"])

    assert data["cards"][0]["sellPrice"] is None
    assert data["cards"][0]["maxSellQuantity"] == 0
    assert data["cards"][0]["lastObtainedAt"] is None


@pytest.fixture()
def cards_table(monkeypatch):
    def owned(owned_id, file_name, name, rarity, obtained_at):
        return {
            "ownedCardId": owned_id,
            "name": name,
            "rarity": rarity,
            "file_name": file_name,
            "obtainedAt": obtained_at,
        }

    table = MagicMock()
    table.query.return_value = {
        "Items": [
            owned("1", "bruma", "Bruma", 3, "2026-01-03"),
            owned("2", "agata", "Ágata", 5, "2026-01-01"),
            owned("3", "astra-3", "astra", 3, "2026-01-02"),
            owned("4", "astra-1", "Astra", 1, "2026-01-04"),
            owned("5", "bruma", "Bruma", 3, "2026-01-01"),
        ]
    }
    monkeypatch.setattr(get_user_cards, "_table", table)
    return table


def get_card_ids(authenticated_event, **query):
    ret = get_user_cards.lambda_handler(
        authenticated_event(queryStringParameters=query or None), ""
    )
    assert ret["statusCode"] == 200
    return [card["file_name"] for card in json.loads(ret["body"])["cards"]]


def test_get_user_cards_default_sort_is_obtained_at_desc(authenticated_event, cards_table):
    # Grupos usam a cópia mais recente: "bruma" tem uma de 01-03.
    assert get_card_ids(authenticated_event) == ["astra-1", "bruma", "astra-3", "agata"]


@pytest.mark.parametrize(
    "query, expected",
    [
        ({"sort": "rarity", "order": "desc"}, ["agata", "astra-3", "bruma", "astra-1"]),
        ({"sort": "rarity", "order": "asc"}, ["astra-1", "astra-3", "bruma", "agata"]),
        ({"sort": "rarity"}, ["agata", "astra-3", "bruma", "astra-1"]),
        ({"sort": "name", "order": "asc"}, ["agata", "astra-1", "astra-3", "bruma"]),
        ({"sort": "name", "order": "desc"}, ["bruma", "astra-1", "astra-3", "agata"]),
        ({"sort": "obtainedAt", "order": "asc"}, ["agata", "astra-3", "bruma", "astra-1"]),
        ({"sort": "quantity", "order": "desc"}, ["bruma", "agata", "astra-1", "astra-3"]),
        ({"sort": "quantity", "order": "asc"}, ["agata", "astra-1", "astra-3", "bruma"]),
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
