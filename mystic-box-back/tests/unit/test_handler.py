import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

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


def fake_dynamodb(table):
    resource = MagicMock()
    resource.Table.return_value = table
    return resource


def test_open_box_handler(apigw_event):
    ret = open_box.lambda_handler(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"
    assert len(data["cards"]) == 1
    assert data["cards"][0] in open_box.CHARACTERS


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
    monkeypatch.setattr(get_user_cards, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(get_user_cards.boto3, "resource", lambda _: fake_dynamodb(table))

    ret = get_user_cards.lambda_handler(authenticated_event(), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["cards"][0]["ownedCardId"] == "owned-1"
    assert data["cards"][0]["name"] == "Astra"
    table.query.assert_called_once()


def test_get_user_cards_handles_dynamodb_error(authenticated_event, monkeypatch):
    table = MagicMock()
    table.query.side_effect = ClientError({"Error": {"Code": "500"}}, "Query")
    monkeypatch.setattr(get_user_cards, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(get_user_cards.boto3, "resource", lambda _: fake_dynamodb(table))

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


def test_save_user_card_stores_card(authenticated_event, monkeypatch):
    table = MagicMock()
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(save_user_card.boto3, "resource", lambda _: fake_dynamodb(table))

    ret = save_user_card.lambda_handler(
        authenticated_event(
            httpMethod="POST",
            body=json.dumps(
                {"card": {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}}
            ),
        ),
        "",
    )
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["card"]["userId"] == "user-123"
    assert data["card"]["name"] == "Astra"
    assert data["card"]["ownedCardId"]
    assert data["card"]["obtainedAt"]

    saved_item = table.put_item.call_args.kwargs["Item"]
    assert saved_item["userId"] == "user-123"
    assert saved_item["name"] == "Astra"
    assert saved_item["file_name"] == "astra.jfif"


def test_save_user_card_handles_dynamodb_error(authenticated_event, monkeypatch):
    table = MagicMock()
    table.put_item.side_effect = ClientError({"Error": {"Code": "500"}}, "PutItem")
    monkeypatch.setattr(save_user_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(save_user_card.boto3, "resource", lambda _: fake_dynamodb(table))

    ret = save_user_card.lambda_handler(
        authenticated_event(
            httpMethod="POST",
            body=json.dumps(
                {"card": {"name": "Astra", "rarity": 5, "file_name": "astra.jfif"}}
            ),
        ),
        "",
    )

    assert ret["statusCode"] == 500
