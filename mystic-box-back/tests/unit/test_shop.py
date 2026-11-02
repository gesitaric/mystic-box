import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mystic_shared import cards

from buy_card import app as buy_card
from get_shop_cards import app as get_shop_cards


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


def wallet_item(balance):
    return {"Item": {"userId": {"S": "user-123"}, "balance": {"N": str(balance)}}}


# ---------- get_shop_cards ----------


@pytest.fixture()
def shop_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(get_shop_cards, "_client", client)
    monkeypatch.setattr(get_shop_cards, "USER_WALLET_TABLE", "wallet")
    client.get_item.return_value = wallet_item(50)
    return client


def test_get_shop_cards_options(apigw_event):
    ret = get_shop_cards.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_get_shop_cards_requires_authentication(apigw_event):
    ret = get_shop_cards.lambda_handler(dict(apigw_event, httpMethod="GET"), "")

    assert ret["statusCode"] == 401


def test_get_shop_cards_lists_catalog_with_server_prices(authenticated_event, shop_client):
    ret = get_shop_cards.lambda_handler(authenticated_event(httpMethod="GET"), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["balance"] == 50
    assert len(data["cards"]) == len(cards.CHARACTERS)

    by_name = {card["name"]: card for card in data["cards"]}
    assert by_name["Astra"] == {
        "name": "Astra",
        "rarity": 5,
        "file_name": "astra.jfif",
        "buyPrice": 250,
        "canAfford": False,
    }
    assert by_name["Kaito"]["canAfford"] is True
    assert by_name["Rowan"]["canAfford"] is True

    key = shop_client.get_item.call_args.kwargs["Key"]
    assert key == {"userId": {"S": "user-123"}}


def test_get_shop_cards_user_without_wallet_has_zero(authenticated_event, shop_client):
    shop_client.get_item.return_value = {}

    ret = get_shop_cards.lambda_handler(authenticated_event(httpMethod="GET"), "")
    data = json.loads(ret["body"])

    assert data["balance"] == 0
    assert not any(card["canAfford"] for card in data["cards"])


def test_get_shop_cards_handles_dynamodb_error(authenticated_event, shop_client):
    shop_client.get_item.side_effect = ClientError({"Error": {"Code": "500"}}, "GetItem")

    ret = get_shop_cards.lambda_handler(authenticated_event(httpMethod="GET"), "")

    assert ret["statusCode"] == 500


# ---------- buy_card ----------


@pytest.fixture()
def buy_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(buy_card, "_client", client)
    monkeypatch.setattr(buy_card, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(buy_card, "USER_WALLET_TABLE", "wallet")
    monkeypatch.setattr(buy_card.time, "time", lambda: 10_000)
    client.get_item.return_value = wallet_item(15)
    return client


def buy(authenticated_event, file_name="astra.jfif", **overrides):
    return buy_card.lambda_handler(
        authenticated_event(
            httpMethod="POST",
            pathParameters={"fileName": file_name},
            **overrides,
        ),
        "",
    )


def test_buy_card_options(apigw_event):
    ret = buy_card.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


def test_buy_card_requires_authentication(apigw_event):
    ret = buy_card.lambda_handler(
        dict(apigw_event, httpMethod="POST", pathParameters={"fileName": "astra.jfif"}),
        "",
    )

    assert ret["statusCode"] == 401


def test_buy_card_debits_server_price_and_adds_card(authenticated_event, buy_client):
    # Preço, nome e raridade enviados pelo cliente são ignorados.
    body = json.dumps({"price": 1, "name": "Malachar", "rarity": 5})
    ret = buy(authenticated_event, body=body)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["price"] == 250
    assert data["balance"] == 15
    assert data["card"]["name"] == "Astra"
    assert data["card"]["rarity"] == 5
    assert data["card"]["file_name"] == "astra.jfif"
    assert data["card"]["sellPrice"] == 250
    assert data["card"]["ownedCardId"]

    update, put = buy_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert update["Update"]["TableName"] == "wallet"
    assert update["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert update["Update"]["ConditionExpression"] == "balance >= :price"
    assert update["Update"]["ExpressionAttributeValues"] == {":price": {"N": "250"}}
    assert put["Put"]["TableName"] == "user-cards"
    assert put["Put"]["Item"]["userId"] == {"S": "user-123"}
    assert put["Put"]["Item"]["name"] == {"S": "Astra"}
    assert put["Put"]["Item"]["rarity"] == {"N": "5"}
    assert put["Put"]["Item"]["file_name"] == {"S": "astra.jfif"}
    assert put["Put"]["Item"]["ownedCardId"] == {"S": data["card"]["ownedCardId"]}
    assert "price" not in put["Put"]["Item"]


def test_buy_card_uses_buy_price_rule(authenticated_event, buy_client, monkeypatch):
    monkeypatch.setattr(buy_card, "buy_price", lambda character: 7)

    ret = buy(authenticated_event, "rowan.jfif")

    assert json.loads(ret["body"])["price"] == 7
    update = buy_client.transact_write_items.call_args.kwargs["TransactItems"][0]
    assert update["Update"]["ExpressionAttributeValues"] == {":price": {"N": "7"}}


@pytest.mark.parametrize(
    "file_name", [None, "", "nao-existe.jfif", "x" * 65, "../astra.jfif"]
)
def test_buy_card_rejects_unknown_card(authenticated_event, buy_client, file_name):
    ret = buy(authenticated_event, file_name)

    assert ret["statusCode"] == 404
    buy_client.transact_write_items.assert_not_called()


def test_buy_card_rejects_card_not_in_catalog(authenticated_event, buy_client, monkeypatch):
    monkeypatch.setattr(
        buy_card, "shop_catalog", lambda: [cards.get_character("rowan.jfif")]
    )

    ret = buy(authenticated_event, "astra.jfif")

    assert ret["statusCode"] == 404
    buy_client.transact_write_items.assert_not_called()


def test_buy_card_insufficient_balance(authenticated_event, buy_client):
    buy_client.transact_write_items.side_effect = transaction_conflict(0)

    ret = buy(authenticated_event)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 409
    assert data["price"] == 250
    assert data["balance"] == 15


def test_buy_card_handles_dynamodb_error(authenticated_event, buy_client):
    buy_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = buy(authenticated_event)

    assert ret["statusCode"] == 500


def test_buy_card_balance_read_failure_still_succeeds(authenticated_event, buy_client):
    buy_client.get_item.side_effect = ClientError({"Error": {"Code": "500"}}, "GetItem")

    ret = buy(authenticated_event, "kaito.jfif")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["price"] == 50
    assert data["balance"] is None
