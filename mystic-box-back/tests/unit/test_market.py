"""Taxa de venda, ordens de compra e histórico de preços do mercado."""

import json

import pytest
from mystic_shared import cards, market

from buy_listing import app as buy_listing
from buy_orders import app as buy_orders
from create_listing import app as create_listing
from shop_listings import app as shop_listings
from tests.unit.fake_dynamo import FakeDynamo

BUYER = "buyer-1"
SELLER = "seller-1"
NOW = 1_800_000_000

TABLES = {
    "orders": ("orderId", None),
    "listings": ("listingId", None),
    "cards": ("userId", "ownedCardId"),
    "wallet": ("userId", None),
    "sales": ("file_name", "saleId"),
}

TABLE_SETTINGS = {
    "BUY_ORDERS_TABLE": "orders",
    "SHOP_LISTINGS_TABLE": "listings",
    "USER_CARDS_TABLE": "cards",
    "USER_WALLET_TABLE": "wallet",
    "MARKET_SALES_TABLE": "sales",
}


# ---------------------------------------------------------------- taxa ---


@pytest.mark.parametrize(
    "price, fee",
    [(1, 1), (5, 1), (14, 1), (15, 2), (300, 30), (2500, 250), (12500, 1250)],
)
def test_market_fee_rounds_with_a_minimum(price, fee):
    assert cards.market_fee(price) == fee
    assert cards.seller_proceeds(price) == price - fee


def test_market_fee_never_exceeds_the_price():
    assert cards.market_fee(0) == 0
    assert all(cards.seller_proceeds(price) >= 0 for price in range(0, 50))


def test_fee_applies_to_every_listing_price():
    for limits in cards.LISTING_PRICE_LIMITS.values():
        assert cards.seller_proceeds(limits["min"]) > 0


def test_summarize_sales():
    assert market.summarize_sales([]) is None
    assert market.summarize_sales([30, 10, 20]) == {
        "count": 3, "last": 30, "average": 20, "min": 10, "max": 30,
    }


# ------------------------------------------------------------ apoio ---


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo(TABLES)
    for module in (buy_orders, buy_listing, create_listing, shop_listings):
        monkeypatch.setattr(module, "_client", fake)
        for name, value in TABLE_SETTINGS.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
        monkeypatch.setattr(module.time, "time", lambda: NOW)
    return fake


def set_wallet(db, user, balance, **counters):
    item = {"userId": {"S": user}, "balance": {"N": str(balance)}}
    item.update({name: {"N": str(value)} for name, value in counters.items()})
    db.tables["wallet"][(user, None)] = item


def wallet(db, user, field="balance"):
    item = db.tables["wallet"].get((user, None), {})
    return int(float(item.get(field, {"N": "0"})["N"]))


def give_card(db, user, owned_id, file_name, obtained_at="2026-01-01T00:00:00+00:00"):
    db.tables["cards"][(user, owned_id)] = {
        "userId": {"S": user},
        "ownedCardId": {"S": owned_id},
        "obtainedAt": {"S": obtained_at},
        "file_name": {"S": file_name},
    }


def cards_of(db, user, file_name=None):
    return [
        item for (owner, _), item in db.tables["cards"].items()
        if owner == user and (file_name is None or item["file_name"]["S"] == file_name)
    ]


def add_listing(db, listing_id, seller, file_name, price):
    db.tables["listings"][(listing_id, None)] = {
        "listingId": {"S": listing_id},
        "sellerId": {"S": seller},
        "ownedCardId": {"S": f"owned-{listing_id}"},
        "file_name": {"S": file_name},
        "price": {"N": str(price)},
        "listedAt": {"S": "2026-01-01T00:00:00+00:00"},
    }


def call(module, authenticated_event, user, method, resource, body=None, path=None, query=None):
    ret = module.lambda_handler(
        authenticated_event(
            sub=user,
            httpMethod=method,
            resource=resource,
            body=json.dumps(body) if body is not None else None,
            pathParameters=path,
            queryStringParameters=query,
        ),
        "",
    )
    return ret["statusCode"], json.loads(ret["body"])


def place(authenticated_event, user=BUYER, file_name="rowan.jfif", price=40):
    return call(buy_orders, authenticated_event, user, "POST", buy_orders.CREATE_ROUTE,
                body={"fileName": file_name, "price": price})


def fill(authenticated_event, order_id, user=SELLER):
    return call(buy_orders, authenticated_event, user, "POST", buy_orders.FILL_ROUTE,
                path={"orderId": order_id})


def cancel(authenticated_event, order_id, user=BUYER):
    return call(buy_orders, authenticated_event, user, "POST", buy_orders.CANCEL_ROUTE,
                path={"orderId": order_id})


# ---------------------------------------------------------- pedir ---


def test_place_order_sets_the_shards_aside(authenticated_event, db):
    set_wallet(db, BUYER, 100)

    # Nome, raridade e qualquer campo extra do cliente são ignorados.
    status, data = call(buy_orders, authenticated_event, BUYER, "POST", buy_orders.CREATE_ROUTE,
                        body={"fileName": "rowan.jfif", "price": 40, "rarity": 5, "name": "X"})

    assert status == 201
    assert data["balance"] == 60
    assert data["order"]["name"] == "Rowan"
    assert data["order"]["rarity"] == 3
    assert wallet(db, BUYER, "activeOrders") == 1
    stored = db.tables["orders"][(data["order"]["orderId"], None)]
    assert stored["buyerId"] == {"S": BUYER}
    assert stored["price"] == {"N": "40"}


def test_place_order_needs_enough_balance(authenticated_event, db):
    set_wallet(db, BUYER, 39)

    status, data = place(authenticated_event)

    assert status == 409
    assert data["balance"] == 39
    assert db.tables["orders"] == {}


def test_place_order_without_wallet(authenticated_event, db):
    status, _ = place(authenticated_event)

    assert status == 409
    assert db.tables["orders"] == {}


def test_place_order_limit_of_active_orders(authenticated_event, db):
    set_wallet(db, BUYER, 1000, activeOrders=cards.MAX_ACTIVE_ORDERS)

    status, data = place(authenticated_event)

    assert status == 409
    assert data["maxActiveOrders"] == cards.MAX_ACTIVE_ORDERS
    assert wallet(db, BUYER) == 1000


@pytest.mark.parametrize(
    "body",
    [
        {"price": 40},
        {"fileName": "rowan.jfif"},
        {"fileName": "rowan.jfif", "price": "40"},
        {"fileName": "rowan.jfif", "price": True},
        {"fileName": "x" * 65, "price": 40},
    ],
)
def test_place_order_rejects_invalid_body(authenticated_event, db, body):
    status, _ = call(buy_orders, authenticated_event, BUYER, "POST", buy_orders.CREATE_ROUTE,
                     body=body)

    assert status == 400


def test_place_order_price_must_be_in_the_rarity_range(authenticated_event, db):
    set_wallet(db, BUYER, 100_000)
    limits = cards.LISTING_PRICE_LIMITS[3]

    for price in (limits["min"] - 1, limits["max"] + 1):
        status, data = place(authenticated_event, price=price)
        assert status == 400
        assert data["priceRange"] == limits


def test_place_order_unknown_card(authenticated_event, db):
    set_wallet(db, BUYER, 100)

    status, _ = place(authenticated_event, file_name="antiga.jfif")

    assert status == 409


def test_place_order_refused_when_a_cheaper_copy_is_on_sale(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    add_listing(db, "l-cheap", SELLER, "rowan.jfif", 30)
    add_listing(db, "l-other-card", SELLER, "kaito.jfif", 5)
    add_listing(db, "l-mine", BUYER, "rowan.jfif", 5)

    status, data = place(authenticated_event, price=40)

    assert status == 409
    assert data["listing"] == {"listingId": "l-cheap", "price": 30}
    assert wallet(db, BUYER) == 100

    # Abaixo do anúncio mais barato, pode pedir.
    status, _ = place(authenticated_event, price=29)
    assert status == 201


# --------------------------------------------------------- cancelar ---


def test_cancel_order_refunds_the_shards(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    _, placed = place(authenticated_event)
    order_id = placed["order"]["orderId"]

    status, data = cancel(authenticated_event, order_id)

    assert status == 200
    assert data["refunded"] == 40
    assert data["balance"] == 100
    assert wallet(db, BUYER, "activeOrders") == 0
    assert db.tables["orders"] == {}

    status, _ = cancel(authenticated_event, order_id)
    assert status == 404


def test_cannot_cancel_another_players_order(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    _, placed = place(authenticated_event)

    status, _ = cancel(authenticated_event, placed["order"]["orderId"], user=SELLER)

    assert status == 404
    assert len(db.tables["orders"]) == 1


# ---------------------------------------------------------- atender ---


def test_fill_order_moves_the_card_and_pays_the_seller(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    set_wallet(db, SELLER, 5)
    give_card(db, SELLER, "old", "rowan.jfif", "2026-01-01T00:00:00+00:00")
    give_card(db, SELLER, "newest", "rowan.jfif", "2026-02-01T00:00:00+00:00")
    _, placed = place(authenticated_event)
    order_id = placed["order"]["orderId"]

    status, data = fill(authenticated_event, order_id)

    assert status == 200
    assert data["price"] == 40
    assert data["fee"] == cards.market_fee(40)
    assert data["proceeds"] == 40 - cards.market_fee(40)
    assert data["balance"] == 5 + data["proceeds"]
    # A cópia mais recente sai do vendedor e uma cópia nova entra no comprador.
    assert [item["ownedCardId"]["S"] for item in cards_of(db, SELLER)] == ["old"]
    assert len(cards_of(db, BUYER, "rowan.jfif")) == 1
    # O comprador já tinha pago ao pedir; só libera a vaga de ordem.
    assert wallet(db, BUYER) == 60
    assert wallet(db, BUYER, "activeOrders") == 0
    assert db.tables["orders"] == {}
    (sale,) = db.tables["sales"].values()
    assert sale["file_name"] == {"S": "rowan.jfif"}
    assert sale["price"] == {"N": "40"}
    assert sale["saleId"]["S"].endswith(f"#{order_id}")
    assert int(sale["expiresAt"]["N"]) == NOW + cards.MARKET_HISTORY_DAYS * 86400

    status, _ = fill(authenticated_event, order_id)
    assert status == 404


def test_cannot_fill_own_order(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    give_card(db, BUYER, "c1", "rowan.jfif")
    _, placed = place(authenticated_event)

    status, _ = fill(authenticated_event, placed["order"]["orderId"], user=BUYER)

    assert status == 409
    assert len(db.tables["orders"]) == 1


def test_fill_order_needs_a_copy(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    give_card(db, SELLER, "c1", "kaito.jfif")
    _, placed = place(authenticated_event)

    status, _ = fill(authenticated_event, placed["order"]["orderId"])

    assert status == 409
    assert len(db.tables["orders"]) == 1
    assert wallet(db, BUYER) == 60


def test_fill_missing_order(authenticated_event, db):
    status, _ = fill(authenticated_event, "missing")
    assert status == 404


def test_unknown_route(authenticated_event, db):
    status, _ = call(buy_orders, authenticated_event, BUYER, "GET", buy_orders.CREATE_ROUTE)
    assert status == 404


# -------------------------------------------- anunciar contra ordem ---


def test_listing_refused_when_a_request_pays_as_much(authenticated_event, db):
    set_wallet(db, BUYER, 100)
    give_card(db, SELLER, "c1", "rowan.jfif")
    _, placed = place(authenticated_event, price=40)

    status, data = call(create_listing, authenticated_event, SELLER, "POST", "/shop/listings",
                        body={"fileName": "rowan.jfif", "quantity": 1, "price": 40})

    assert status == 409
    assert data["order"] == {"orderId": placed["order"]["orderId"], "price": 40}
    assert len(cards_of(db, SELLER)) == 1

    # Acima da ordem, pode anunciar; a resposta diz quanto ele recebe.
    status, data = call(create_listing, authenticated_event, SELLER, "POST", "/shop/listings",
                        body={"fileName": "rowan.jfif", "quantity": 1, "price": 41})
    assert status == 201
    assert data["fee"] == cards.market_fee(41)
    assert data["proceeds"] == 41 - cards.market_fee(41)


def test_own_request_does_not_block_listing(authenticated_event, db):
    set_wallet(db, SELLER, 100)
    give_card(db, SELLER, "c1", "rowan.jfif")
    place(authenticated_event, user=SELLER, price=40)

    status, _ = call(create_listing, authenticated_event, SELLER, "POST", "/shop/listings",
                     body={"fileName": "rowan.jfif", "quantity": 1, "price": 20})

    assert status == 201


# ------------------------------------------------------- vitrine ---


def test_shop_shows_requests_and_order_options(authenticated_event, db):
    set_wallet(db, BUYER, 500)
    set_wallet(db, "buyer-2", 500)
    set_wallet(db, SELLER, 50)
    give_card(db, SELLER, "c1", "rowan.jfif")
    place(authenticated_event, user=BUYER, file_name="rowan.jfif", price=30)
    _, best = place(authenticated_event, user="buyer-2", file_name="rowan.jfif", price=45)
    place(authenticated_event, user=BUYER, file_name="astra.jfif", price=200)
    _, mine = place(authenticated_event, user=SELLER, file_name="kaito.jfif", price=25)

    status, data = call(shop_listings, authenticated_event, SELLER, "GET", "/shop/listings")

    assert status == 200
    assert data["balance"] == 25
    assert data["marketFeePercent"] == cards.MARKET_FEE_PERCENT
    assert data["maxActiveOrders"] == cards.MAX_ACTIVE_ORDERS
    # Primeiro o que o jogador pode atender; em cada carta, a maior ordem.
    assert data["orders"] == [
        {
            "name": "Rowan",
            "rarity": 3,
            "file_name": "rowan.jfif",
            "wanted": 2,
            "orderId": best["order"]["orderId"],
            "price": 45,
            "fee": cards.market_fee(45),
            "proceeds": 45 - cards.market_fee(45),
            "owned": 1,
            "canFill": True,
        },
        {
            "name": "Astra",
            "rarity": 5,
            "file_name": "astra.jfif",
            "wanted": 1,
            "orderId": data["orders"][1]["orderId"],
            "price": 200,
            "fee": cards.market_fee(200),
            "proceeds": 200 - cards.market_fee(200),
            "owned": 0,
            "canFill": False,
        },
    ]
    assert [order["orderId"] for order in data["myOrders"]] == [mine["order"]["orderId"]]
    assert data["reservedBalance"] == 25
    assert len(data["orderOptions"]) == len(cards.CHARACTERS)
    astra = next(o for o in data["orderOptions"] if o["file_name"] == "astra.jfif")
    assert astra["priceRange"] == cards.LISTING_PRICE_LIMITS[5]
    assert [o["rarity"] for o in data["orderOptions"]] == sorted(
        (o["rarity"] for o in data["orderOptions"]), reverse=True
    )


# ------------------------------------------------------- histórico ---


def history(authenticated_event, file_name):
    return call(shop_listings, authenticated_event, BUYER, "GET", shop_listings.HISTORY_ROUTE,
                query={"fileName": file_name} if file_name is not None else None)


def test_history_lists_recent_sales_newest_first(authenticated_event, db):
    for index, price in enumerate([20, 35, 50]):
        sold_at = f"2027-01-0{index + 1}T00:00:00+00:00"
        put = market.sale_record_put("sales", "rowan.jfif", price, sold_at, f"s{index}", NOW)
        db.tables["sales"][("rowan.jfif", put["Put"]["Item"]["saleId"]["S"])] = put["Put"]["Item"]

    status, data = history(authenticated_event, "rowan.jfif")

    assert status == 200
    assert data["days"] == cards.MARKET_HISTORY_DAYS
    assert [sale["price"] for sale in data["sales"]] == [50, 35, 20]
    assert data["sales"][0]["soldAt"] == "2027-01-03T00:00:00+00:00"
    assert data["summary"] == {"count": 3, "last": 50, "average": 35, "min": 20, "max": 50}


def test_history_skips_expired_sales(authenticated_event, db):
    put = market.sale_record_put("sales", "rowan.jfif", 20, "2020-01-01T00:00:00+00:00", "s0",
                                 NOW - cards.MARKET_HISTORY_DAYS * 86400 - 1)
    db.tables["sales"][("rowan.jfif", put["Put"]["Item"]["saleId"]["S"])] = put["Put"]["Item"]

    status, data = history(authenticated_event, "rowan.jfif")

    assert status == 200
    assert data["sales"] == []
    assert data["summary"] is None


def test_history_requires_a_known_card(authenticated_event, db):
    assert history(authenticated_event, None)[0] == 400
    assert history(authenticated_event, "antiga.jfif")[0] == 404


def test_history_records_sales_from_both_paths(authenticated_event, db):
    """Compra de anúncio e ordem atendida entram no mesmo histórico."""
    set_wallet(db, BUYER, 1000)
    set_wallet(db, SELLER, 0, activeListings=1)
    add_listing(db, "l1", SELLER, "rowan.jfif", 60)
    status, _ = call(buy_listing, authenticated_event, BUYER, "POST", "/shop/listings/{listingId}/buy",
                     path={"listingId": "l1"})
    assert status == 201
    assert wallet(db, SELLER) == 60 - cards.market_fee(60)

    give_card(db, SELLER, "c1", "rowan.jfif")
    _, placed = place(authenticated_event, price=40)
    assert fill(authenticated_event, placed["order"]["orderId"])[0] == 200

    _, data = history(authenticated_event, "rowan.jfif")
    assert sorted(sale["price"] for sale in data["sales"]) == [40, 60]
