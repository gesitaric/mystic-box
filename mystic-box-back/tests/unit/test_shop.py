import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mystic_shared import cards

from buy_listing import app as buy_listing
from cancel_listing import app as cancel_listing
from create_listing import app as create_listing
from shop_listings import app as shop_listings


def transaction_conflict(*failed_indexes, size):
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


def listing_item(listing_id, seller, file_name, price, listed_at="2026-01-01T00:00:00+00:00"):
    character = cards.get_character(file_name)
    return {
        "listingId": {"S": listing_id},
        "sellerId": {"S": seller},
        "ownedCardId": {"S": f"owned-{listing_id}"},
        "obtainedAt": {"S": "2025-12-01T00:00:00+00:00"},
        "name": {"S": character["name"] if character else "Antiga"},
        "rarity": {"N": str(character["rarity"] if character else 3)},
        "file_name": {"S": file_name},
        "price": {"N": str(price)},
        "listedAt": {"S": listed_at},
    }


@pytest.mark.parametrize("module", [shop_listings, create_listing, buy_listing, cancel_listing])
def test_options(apigw_event, module):
    ret = module.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")

    assert ret["statusCode"] == 200
    assert ret["headers"]["Access-Control-Allow-Origin"] == "*"


@pytest.mark.parametrize("module", [shop_listings, create_listing, buy_listing, cancel_listing])
def test_requires_authentication(apigw_event, module):
    ret = module.lambda_handler(
        dict(apigw_event, httpMethod="POST", pathParameters={"listingId": "l1"}), ""
    )

    assert ret["statusCode"] == 401


# ---------- shop_listings ----------


@pytest.fixture()
def shop_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(shop_listings, "_client", client)
    monkeypatch.setattr(shop_listings, "SHOP_LISTINGS_TABLE", "listings")
    monkeypatch.setattr(shop_listings, "USER_WALLET_TABLE", "wallet")
    client.get_item.return_value = wallet_item(300)
    client.scan.return_value = {
        "Items": [
            listing_item("a-exp", "other", "astra.jfif", 900),
            listing_item("a-cheap", "other-2", "astra.jfif", 280),
            listing_item("r1", "other", "rowan.jfif", 20),
            listing_item("mine-1", "user-123", "kaito.jfif", 60, "2026-01-01T00:00:00+00:00"),
            listing_item("mine-2", "user-123", "rowan.jfif", 15, "2026-01-02T00:00:00+00:00"),
            listing_item("old", "other", "antiga.jfif", 10),
        ]
    }
    return client


def test_shop_lists_only_cards_other_players_put_up_for_sale(authenticated_event, shop_client):
    ret = shop_listings.lambda_handler(authenticated_event(httpMethod="GET"), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["balance"] == 300
    assert data["maxActiveListings"] == cards.MAX_ACTIVE_LISTINGS
    # Agrupado por carta, mostrando o anúncio mais barato; sem os do próprio jogador.
    assert data["cards"] == [
        {
            "name": "Astra",
            "rarity": 5,
            "file_name": "astra.jfif",
            "available": 2,
            "listingId": "a-cheap",
            "price": 280,
            "canAfford": True,
        },
        {
            "name": "Rowan",
            "rarity": 3,
            "file_name": "rowan.jfif",
            "available": 1,
            "listingId": "r1",
            "price": 20,
            "canAfford": True,
        },
    ]
    assert [listing["listingId"] for listing in data["myListings"]] == ["mine-2", "mine-1"]
    assert data["myListings"][0] == {
        "listingId": "mine-2",
        "name": "Rowan",
        "rarity": 3,
        "file_name": "rowan.jfif",
        "price": 15,
        "listedAt": "2026-01-02T00:00:00+00:00",
    }


def test_shop_is_empty_without_listings(authenticated_event, shop_client):
    shop_client.scan.return_value = {"Items": []}

    data = json.loads(
        shop_listings.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"]
    )

    assert data["cards"] == []
    assert data["myListings"] == []


def test_shop_can_afford_uses_server_balance(authenticated_event, shop_client):
    shop_client.get_item.return_value = {}

    data = json.loads(
        shop_listings.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"]
    )

    assert data["balance"] == 0
    assert not any(card["canAfford"] for card in data["cards"])


def test_shop_reads_every_page(authenticated_event, shop_client):
    shop_client.scan.return_value = None
    shop_client.scan.side_effect = [
        {"Items": [listing_item("r1", "other", "rowan.jfif", 20)], "LastEvaluatedKey": {"k": 1}},
        {"Items": [listing_item("r2", "other", "rowan.jfif", 10)]},
    ]

    data = json.loads(
        shop_listings.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"]
    )

    assert data["cards"][0]["available"] == 2
    assert data["cards"][0]["listingId"] == "r2"
    assert shop_client.scan.call_args_list[1].kwargs["ExclusiveStartKey"] == {"k": 1}


def test_shop_handles_dynamodb_error(authenticated_event, shop_client):
    shop_client.scan.side_effect = ClientError({"Error": {"Code": "500"}}, "Scan")

    ret = shop_listings.lambda_handler(authenticated_event(httpMethod="GET"), "")

    assert ret["statusCode"] == 500


# ---------- create_listing ----------


def owned_copies(*copies):
    """Resposta do Query: (ownedCardId, obtainedAt) de cada cópia."""
    return {
        "Items": [
            {"ownedCardId": {"S": owned_id}, "obtainedAt": {"S": obtained_at}}
            for owned_id, obtained_at in copies
        ]
    }


@pytest.fixture()
def create_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(create_listing, "_client", client)
    monkeypatch.setattr(create_listing, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(create_listing, "USER_WALLET_TABLE", "wallet")
    monkeypatch.setattr(create_listing, "SHOP_LISTINGS_TABLE", "listings")
    monkeypatch.setattr(create_listing.time, "time", lambda: 10_000)
    client.query.return_value = owned_copies(
        ("old", "2026-01-01T00:00:00+00:00"),
        ("newest", "2026-01-03T00:00:00+00:00"),
        ("middle", "2026-01-02T00:00:00+00:00"),
    )
    return client


def create(authenticated_event, body=None):
    body = {"fileName": "astra.jfif", "quantity": 2, "price": 300} if body is None else body
    return create_listing.lambda_handler(
        authenticated_event(httpMethod="POST", body=json.dumps(body)), ""
    )


def test_create_listing_moves_newest_copies_to_the_shop(authenticated_event, create_client):
    # Nome e raridade enviados pelo cliente são ignorados.
    ret = create(
        authenticated_event,
        {"fileName": "astra.jfif", "quantity": 2, "price": 300, "name": "X", "rarity": 3},
    )
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["listedQuantity"] == 2
    assert data["remainingQuantity"] == 1
    assert data["price"] == 300
    assert len(data["listingIds"]) == 2

    items = create_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 5
    deletes, puts, wallet = items[:2], items[2:4], items[4]

    assert [d["Delete"]["Key"]["ownedCardId"]["S"] for d in deletes] == ["newest", "middle"]
    for delete in deletes:
        assert delete["Delete"]["TableName"] == "user-cards"
        assert delete["Delete"]["Key"]["userId"] == {"S": "user-123"}
        assert "attribute_exists(ownedCardId)" in delete["Delete"]["ConditionExpression"]

    for put, owned_id, listing_id in zip(puts, ["newest", "middle"], data["listingIds"]):
        item = put["Put"]["Item"]
        assert put["Put"]["TableName"] == "listings"
        assert item["listingId"] == {"S": listing_id}
        assert item["sellerId"] == {"S": "user-123"}
        assert item["ownedCardId"] == {"S": owned_id}
        assert item["name"] == {"S": "Astra"}
        assert item["rarity"] == {"N": "5"}
        assert item["price"] == {"N": "300"}

    assert wallet["Update"]["TableName"] == "wallet"
    assert wallet["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert wallet["Update"]["ExpressionAttributeValues"] == {
        ":quantity": {"N": "2"},
        ":limit": {"N": str(cards.MAX_ACTIVE_LISTINGS - 2)},
    }


@pytest.mark.parametrize(
    "price", [cards.LISTING_PRICE_LIMITS[5]["min"] - 1, cards.LISTING_PRICE_LIMITS[5]["max"] + 1]
)
def test_create_listing_rejects_price_outside_rarity_range(authenticated_event, create_client, price):
    ret = create(authenticated_event, {"fileName": "astra.jfif", "quantity": 1, "price": price})

    assert ret["statusCode"] == 400
    assert json.loads(ret["body"])["priceRange"] == cards.LISTING_PRICE_LIMITS[5]
    create_client.transact_write_items.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        "not a dict",
        {"quantity": 1, "price": 300},
        {"fileName": "astra.jfif", "price": 300},
        {"fileName": "astra.jfif", "quantity": 0, "price": 300},
        {"fileName": "astra.jfif", "quantity": cards.MAX_LISTING_QUANTITY + 1, "price": 300},
        {"fileName": "astra.jfif", "quantity": True, "price": 300},
        {"fileName": "astra.jfif", "quantity": 1},
        {"fileName": "astra.jfif", "quantity": 1, "price": "300"},
        {"fileName": "astra.jfif", "quantity": 1, "price": 300.5},
        {"fileName": "x" * 65, "quantity": 1, "price": 300},
    ],
)
def test_create_listing_rejects_invalid_body(authenticated_event, create_client, body):
    ret = create(authenticated_event, body)

    assert ret["statusCode"] == 400
    create_client.query.assert_not_called()
    create_client.transact_write_items.assert_not_called()


def test_create_listing_unknown_card(authenticated_event, create_client):
    ret = create(authenticated_event, {"fileName": "antiga.jfif", "quantity": 1, "price": 10})

    assert ret["statusCode"] == 409
    create_client.transact_write_items.assert_not_called()


def test_create_listing_card_not_owned(authenticated_event, create_client):
    create_client.query.return_value = {"Items": []}

    ret = create(authenticated_event)

    assert ret["statusCode"] == 404
    create_client.transact_write_items.assert_not_called()


def test_create_listing_rejects_more_than_owned(authenticated_event, create_client):
    ret = create(authenticated_event, {"fileName": "astra.jfif", "quantity": 4, "price": 300})

    assert ret["statusCode"] == 409
    assert json.loads(ret["body"])["available"] == 3
    create_client.transact_write_items.assert_not_called()


def test_create_listing_limit_of_active_listings(authenticated_event, create_client):
    create_client.transact_write_items.side_effect = transaction_conflict(4, size=5)

    ret = create(authenticated_event)

    assert ret["statusCode"] == 409
    assert json.loads(ret["body"])["maxActiveListings"] == cards.MAX_ACTIVE_LISTINGS


def test_create_listing_collection_changed(authenticated_event, create_client):
    create_client.transact_write_items.side_effect = transaction_conflict(1, size=5)

    ret = create(authenticated_event)

    assert ret["statusCode"] == 409
    assert "collection changed" in json.loads(ret["body"])["message"]


def test_create_listing_handles_dynamodb_error(authenticated_event, create_client):
    create_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = create(authenticated_event)

    assert ret["statusCode"] == 500


# ---------- buy_listing ----------


@pytest.fixture()
def buy_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(buy_listing, "_client", client)
    monkeypatch.setattr(buy_listing, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(buy_listing, "USER_WALLET_TABLE", "wallet")
    monkeypatch.setattr(buy_listing, "SHOP_LISTINGS_TABLE", "listings")
    monkeypatch.setattr(buy_listing.time, "time", lambda: 10_000)

    def get_item(TableName, Key, **kwargs):
        if TableName == "listings":
            return {"Item": listing_item("l1", "seller-9", "astra.jfif", 300)}
        return wallet_item(50)

    client.get_item.side_effect = get_item
    return client


def buy(authenticated_event, listing_id="l1", **overrides):
    return buy_listing.lambda_handler(
        authenticated_event(
            httpMethod="POST", pathParameters={"listingId": listing_id}, **overrides
        ),
        "",
    )


def test_buy_listing_pays_seller_and_moves_card(authenticated_event, buy_client):
    # Preço enviado pelo cliente é ignorado: vale o do anúncio.
    ret = buy(authenticated_event, body=json.dumps({"price": 1}))
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 201
    assert data["price"] == 300
    assert data["balance"] == 50
    assert data["card"]["name"] == "Astra"
    assert data["card"]["rarity"] == 5

    delete, buyer, seller, put = buy_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert delete["Delete"]["TableName"] == "listings"
    assert delete["Delete"]["Key"] == {"listingId": {"S": "l1"}}
    assert delete["Delete"]["ExpressionAttributeValues"] == {
        ":seller": {"S": "seller-9"},
        ":price": {"N": "300"},
    }
    assert buyer["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert buyer["Update"]["ConditionExpression"] == "balance >= :price"
    assert buyer["Update"]["ExpressionAttributeValues"] == {":price": {"N": "300"}}
    assert seller["Update"]["Key"] == {"userId": {"S": "seller-9"}}
    assert seller["Update"]["ExpressionAttributeValues"] == {
        ":price": {"N": "300"},
        ":minusOne": {"N": "-1"},
    }
    assert put["Put"]["TableName"] == "user-cards"
    assert put["Put"]["Item"]["userId"] == {"S": "user-123"}
    assert put["Put"]["Item"]["file_name"] == {"S": "astra.jfif"}
    assert put["Put"]["Item"]["ownedCardId"] == {"S": data["card"]["ownedCardId"]}


def test_buy_listing_cannot_buy_own_listing(authenticated_event, buy_client):
    ret = buy(authenticated_event, sub="seller-9")

    assert ret["statusCode"] == 409
    buy_client.transact_write_items.assert_not_called()


def test_buy_listing_missing_listing(authenticated_event, buy_client):
    buy_client.get_item.side_effect = lambda **kwargs: {}

    ret = buy(authenticated_event)

    assert ret["statusCode"] == 409
    buy_client.transact_write_items.assert_not_called()


@pytest.mark.parametrize("listing_id", [None, "", "x" * 65])
def test_buy_listing_invalid_id(authenticated_event, buy_client, listing_id):
    ret = buy(authenticated_event, listing_id)

    assert ret["statusCode"] == 404
    buy_client.get_item.assert_not_called()


def test_buy_listing_sold_in_the_meantime(authenticated_event, buy_client):
    buy_client.transact_write_items.side_effect = transaction_conflict(0, size=4)

    ret = buy(authenticated_event)

    assert ret["statusCode"] == 409
    assert "already sold" in json.loads(ret["body"])["message"]


def test_buy_listing_insufficient_balance(authenticated_event, buy_client):
    buy_client.transact_write_items.side_effect = transaction_conflict(1, size=4)

    ret = buy(authenticated_event)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 409
    assert data["price"] == 300
    assert data["balance"] == 50


def test_buy_listing_handles_dynamodb_error(authenticated_event, buy_client):
    buy_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = buy(authenticated_event)

    assert ret["statusCode"] == 500


# ---------- cancel_listing ----------


@pytest.fixture()
def cancel_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(cancel_listing, "_client", client)
    monkeypatch.setattr(cancel_listing, "USER_CARDS_TABLE", "user-cards")
    monkeypatch.setattr(cancel_listing, "USER_WALLET_TABLE", "wallet")
    monkeypatch.setattr(cancel_listing, "SHOP_LISTINGS_TABLE", "listings")
    client.get_item.return_value = {"Item": listing_item("l1", "user-123", "kaito.jfif", 60)}
    return client


def cancel(authenticated_event, listing_id="l1", **overrides):
    return cancel_listing.lambda_handler(
        authenticated_event(
            httpMethod="POST", pathParameters={"listingId": listing_id}, **overrides
        ),
        "",
    )


def test_cancel_listing_returns_card_to_collection(authenticated_event, cancel_client):
    ret = cancel(authenticated_event)
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["card"]["ownedCardId"] == "owned-l1"
    assert data["card"]["obtainedAt"] == "2025-12-01T00:00:00+00:00"

    delete, put, wallet = cancel_client.transact_write_items.call_args.kwargs["TransactItems"]
    assert delete["Delete"]["Key"] == {"listingId": {"S": "l1"}}
    assert delete["Delete"]["ExpressionAttributeValues"] == {":seller": {"S": "user-123"}}
    assert put["Put"]["TableName"] == "user-cards"
    assert put["Put"]["Item"]["userId"] == {"S": "user-123"}
    assert put["Put"]["Item"]["ownedCardId"] == {"S": "owned-l1"}
    assert put["Put"]["Item"]["name"] == {"S": "Kaito"}
    assert wallet["Update"]["Key"] == {"userId": {"S": "user-123"}}
    assert wallet["Update"]["ExpressionAttributeValues"] == {":minusOne": {"N": "-1"}}


def test_cancel_listing_of_another_player_is_not_found(authenticated_event, cancel_client):
    ret = cancel(authenticated_event, sub="intruder")

    assert ret["statusCode"] == 404
    cancel_client.transact_write_items.assert_not_called()


def test_cancel_listing_missing(authenticated_event, cancel_client):
    cancel_client.get_item.return_value = {}

    ret = cancel(authenticated_event)

    assert ret["statusCode"] == 404


def test_cancel_listing_sold_in_the_meantime(authenticated_event, cancel_client):
    cancel_client.transact_write_items.side_effect = transaction_conflict(0, size=3)

    ret = cancel(authenticated_event)

    assert ret["statusCode"] == 404


def test_cancel_listing_handles_dynamodb_error(authenticated_event, cancel_client):
    cancel_client.transact_write_items.side_effect = ClientError(
        {"Error": {"Code": "500"}}, "TransactWriteItems"
    )

    ret = cancel(authenticated_event)

    assert ret["statusCode"] == 500
