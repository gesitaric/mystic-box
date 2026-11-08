import json

import pytest
from mystic_shared import mastery
from mystic_shared.cards import CHARACTERS

from claim_region import app as claim_region
from tests.unit.fake_dynamo import FakeDynamo

USER = "user-123"


def test_every_champion_belongs_to_one_region():
    placed = [name for region in mastery.regions_with_residents()
              for name in mastery.residents(region)]
    assert sorted(placed) == sorted(c["file_name"] for c in CHARACTERS)


def test_public_collection_counts_owned_champions():
    owned = set(mastery.residents("cinderpeak"))
    rows = {r["region"]: r for r in mastery.public_collection(owned, {"cinderpeak"})}
    assert rows["cinderpeak"]["complete"] is True
    assert rows["cinderpeak"]["claimed"] is True
    assert rows["cinderpeak"]["reward"] == 4 * mastery.COLLECTION_REWARD_PER_CHAMPION
    assert rows["nocthaven"]["owned"] == 0


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo({"cards": ("userId", "ownedCardId"), "regions": ("userId", None),
                       "wallet": ("userId", None)})
    monkeypatch.setattr(claim_region, "_client", fake)
    monkeypatch.setattr(claim_region, "USER_CARDS_TABLE", "cards")
    monkeypatch.setattr(claim_region, "REGION_PROGRESS_TABLE", "regions")
    monkeypatch.setattr(claim_region, "USER_WALLET_TABLE", "wallet")
    return fake


def give(db, *names):
    for index, name in enumerate(names):
        db.tables["cards"][(USER, f"c{index}")] = {
            "userId": {"S": USER}, "ownedCardId": {"S": f"c{index}"},
            "file_name": {"S": name},
        }


def claim(authenticated_event, region_id):
    ret = claim_region.lambda_handler(
        authenticated_event(httpMethod="POST", body=json.dumps({"regionId": region_id})), ""
    )
    return ret["statusCode"], json.loads(ret["body"])


def test_claim_pays_once_for_a_complete_region(authenticated_event, db):
    give(db, *mastery.residents("cinderpeak"))

    status, body = claim(authenticated_event, "cinderpeak")
    assert status == 200
    assert body["reward"] == mastery.collection_reward("cinderpeak")
    assert db.tables["wallet"][(USER, None)]["balance"]["N"] == str(body["reward"])
    assert mastery.claim_attribute("cinderpeak") in db.tables["regions"][(USER, None)]

    status, body = claim(authenticated_event, "cinderpeak")
    assert status == 409
    assert db.tables["wallet"][(USER, None)]["balance"]["N"] == str(
        mastery.collection_reward("cinderpeak")
    )


def test_claim_requires_the_whole_region(authenticated_event, db):
    give(db, *mastery.residents("cinderpeak")[:-1])
    status, _ = claim(authenticated_event, "cinderpeak")
    assert status == 409
    assert (USER, None) not in db.tables["wallet"]


def test_claim_rejects_bad_requests(apigw_event, authenticated_event, db):
    assert claim_region.lambda_handler(apigw_event, "")["statusCode"] == 401
    assert claim(authenticated_event, "riftheart")[0] == 404
    ret = claim_region.lambda_handler(authenticated_event(httpMethod="POST", body="[]"), "")
    assert ret["statusCode"] == 400
