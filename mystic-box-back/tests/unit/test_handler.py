import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from get_summon_status import app as get_summon_status
from get_user_cards import app as get_user_cards
from open_box import app as open_box
from save_user_card import app as save_user_card


@pytest.fixture()
def apigw_event():
    """ Generates API GW Event"""

    return {
        "body": '{ "test": "body"}',
        "resource": "/{proxy+}",
        "requestContext": {
            "resourceId": "123456",
            "apiId": "1234567890",
            "resourcePath": "/{proxy+}",
            "httpMethod": "GET",
            "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
            "accountId": "123456789012",
            "identity": {
                "apiKey": "",
                "userArn": "",
                "cognitoAuthenticationType": "",
                "caller": "",
                "userAgent": "Custom User Agent String",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "127.0.0.1",
                "accountId": "",
            },
            "stage": "prod",
        },
        "queryStringParameters": {"foo": "bar"},
        "headers": {
            "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
            "Accept-Language": "en-US,en;q=0.8",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Custom User Agent String",
            "CloudFront-Forwarded-Proto": "https",
            "Accept-Encoding": "gzip, deflate, sdch",
        },
        "pathParameters": {"proxy": "/examplepath"},
        "httpMethod": "GET",
        "stageVariables": {"baz": "qux"},
        "path": "/examplepath",
    }


@pytest.fixture()
def authenticated_event(apigw_event):
    def build(sub="user-123", **overrides):
        event = dict(apigw_event, **overrides)
        event["requestContext"] = {
            **apigw_event["requestContext"],
            "authorizer": {"claims": {"sub": sub}},
        }
        return event

    return build


CARD_BODY = json.dumps(
    {
        "cards": [
            {"name": "Rowan", "rarity": 3, "file_name": "rowan.jfif"},
            {"name": "Kaito", "rarity": 4, "file_name": "kaito.jfif"},
            {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"},
        ]
    }
)


def cooldown_conflict():
    return ClientError(
        {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [{"Code": "ConditionalCheckFailed"}, {"Code": "None"}],
        },
        "TransactWriteItems",
    )


def test_open_box_handler(apigw_event):
    ret = open_box.lambda_handler(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert len(data["cards"]) == 3
    assert all(card in open_box.CHARACTERS for card in data["cards"])


def test_open_box_cards_never_repeat():
    for _ in range(500):
        names = [card["name"] for card in open_box.draw_cards()]
        assert len(set(names)) == 3


def test_open_box_last_card_uses_boosted_weights(monkeypatch):
    calls = []

    def fake_choices(population, weights, k):
        calls.append(dict(zip((c["name"] for c in population), weights)))
        return [population[0]]

    monkeypatch.setattr(open_box.random, "choices", fake_choices)
    open_box.draw_cards()

    assert len(calls) == 3
    # Os dois primeiros sorteios usam os pesos normais; o último, os reforçados.
    assert calls[0]["Astra"] == open_box.RARITY_WEIGHTS[5]
    assert calls[1]["Astra"] == open_box.RARITY_WEIGHTS[5]
    assert calls[2]["Astra"] == open_box.LAST_CARD_RARITY_WEIGHTS[5]
    assert calls[2]["Kaito"] == open_box.LAST_CARD_RARITY_WEIGHTS[4]
    assert calls[2]["Rowan"] == open_box.LAST_CARD_RARITY_WEIGHTS[3]
    # Personagens já sorteados saem das opções seguintes.
    assert "Malachar" not in calls[1]
    assert "Boreas" not in calls[2]


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


def test_save_user_card_rejects_invalid_body(authenticated_event, monkeypatch):
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")

    ret = save_user_card.lambda_handler(
        authenticated_event(body=json.dumps({"card": {"name": "", "rarity": 9}})),
        "",
    )

    assert ret["statusCode"] == 400


@pytest.fixture()
def save_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(save_user_card, "_client", client)
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(save_user_card, "USER_SUMMON_STATE_TABLE", "summon-state")
    monkeypatch.setattr(save_user_card, "SUMMON_COOLDOWN_SECONDS", 3600)
    monkeypatch.setattr(save_user_card.time, "time", lambda: 10_000)
    return client


def test_save_user_card_stores_card_and_starts_cooldown(authenticated_event, save_client):
    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=CARD_BODY), ""
    )
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert [card["name"] for card in data["cards"]] == ["Rowan", "Kaito", "Astra"]
    assert all(card["userId"] == "user-123" for card in data["cards"])
    assert len({card["ownedCardId"] for card in data["cards"]}) == 3
    assert data["cards"][0]["obtainedAt"]
    assert data["retryAfterSeconds"] == 3600

    update, *puts = save_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(puts) == 3
    put = puts[2]
    assert update["Update"]["TableName"] == "summon-state"
    assert update["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert update["Update"]["ExpressionAttributeValues"] == {
        ":now": {"N": "10000"},
        ":threshold": {"N": "6400"},
    }
    assert put["Put"]["TableName"] == "user-cards"
    assert put["Put"]["Item"]["userId"] == {"S": "user-123"}
    assert put["Put"]["Item"]["name"] == {"S": "Astra"}
    assert put["Put"]["Item"]["rarity"] == {"N": "5"}
    assert put["Put"]["Item"]["file_name"] == {"S": "astra.jfif"}


def test_save_user_card_accepts_legacy_single_card(authenticated_event, save_client):
    ret = save_user_card.lambda_handler(
        authenticated_event(
            httpMethod="POST",
            body=json.dumps(
                {"card": {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}}
            ),
        ),
        "",
    )

    assert ret["statusCode"] == 201
    items = save_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 2


def test_save_user_card_rejects_repeated_cards(authenticated_event, save_client):
    card = {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}

    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=json.dumps({"cards": [card, card]})),
        "",
    )

    assert ret["statusCode"] == 400
    save_client.transact_write_items.assert_not_called()


def test_save_user_card_rejects_too_many_cards(authenticated_event, save_client):
    cards = [
        {"name": name, "rarity": 3, "file_name": f"{name.lower()}.jfif"}
        for name in ("Rowan", "Corvus", "Kaito", "Sylva")
    ]

    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=json.dumps({"cards": cards})),
        "",
    )

    assert ret["statusCode"] == 400
    save_client.transact_write_items.assert_not_called()


def test_save_user_card_rejects_during_cooldown(authenticated_event, save_client):
    save_client.transact_write_items.side_effect = cooldown_conflict()
    save_client.get_item.return_value = {"Item": {"lastSummonAt": {"N": "9000"}}}

    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=CARD_BODY), ""
    )
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 429
    assert ret["headers"]["Retry-After"] == "2600"
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert data["retryAfterSeconds"] == 2600


def test_save_user_card_handles_dynamodb_error(authenticated_event, save_client):
    save_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = save_user_card.lambda_handler(
        authenticated_event(httpMethod="POST", body=CARD_BODY), ""
    )

    assert ret["statusCode"] == 500


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
