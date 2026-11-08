import json

import pytest
from mystic_shared import titles
from mystic_shared.campaign import CAMPAIGN

from set_title import app as set_title
from tests.unit.fake_dynamo import FakeDynamo

USER = "user-123"


def test_title_ids_are_unique_and_every_region_has_two():
    ids = [t["id"] for t in titles.TITLES]
    assert len(ids) == len(set(ids))
    for region_id in CAMPAIGN:
        assert titles.get_title(f"collection_{region_id}")
        assert titles.get_title(f"campaign_{region_id}")


def test_earned_titles_follow_each_condition():
    earned = titles.earned_titles(
        level=10,
        campaign_progress={"nocthaven": 3, "hrimvald": 2},
        claimed={"cinderpeak"},
        ascensions={"ravenna.png": 1, "ignis.jfif": 0},
    )
    assert {"summoner", "arcane_adept", "campaign_nocthaven", "collection_cinderpeak",
            "who_freed_lira"} <= earned
    assert not {"archsummoner", "campaign_hrimvald", "everfire_keeper"} & earned


@pytest.fixture()
def db(monkeypatch):
    fake = FakeDynamo({"profiles": ("userId", None), "progress": ("userId", None),
                       "regions": ("userId", None), "ascensions": ("userId", "file_name")})
    monkeypatch.setattr(set_title, "_client", fake)
    monkeypatch.setattr(set_title, "USER_PROFILES_TABLE", "profiles")
    monkeypatch.setattr(set_title, "USER_PROGRESS_TABLE", "progress")
    monkeypatch.setattr(set_title, "REGION_PROGRESS_TABLE", "regions")
    monkeypatch.setattr(set_title, "CARD_ASCENSIONS_TABLE", "ascensions")
    return fake


def choose(authenticated_event, title_id):
    ret = set_title.lambda_handler(
        authenticated_event(httpMethod="POST", body=json.dumps({"titleId": title_id})), ""
    )
    return ret["statusCode"], json.loads(ret["body"])


def test_choose_an_earned_title_and_remove_it(authenticated_event, db):
    db.tables["ascensions"][(USER, "ravenna.png")] = {
        "userId": {"S": USER}, "file_name": {"S": "ravenna.png"}, "ascension": {"N": "1"},
    }

    status, body = choose(authenticated_event, "who_freed_lira")
    assert status == 200
    assert body["title"] == {"id": "who_freed_lira", "name": "Who Freed Lira"}
    assert db.tables["profiles"][(USER, None)]["title"] == {"S": "who_freed_lira"}

    status, body = choose(authenticated_event, None)
    assert status == 200 and body["title"] is None
    assert "title" not in db.tables["profiles"][(USER, None)]


def test_cannot_choose_a_title_not_earned(authenticated_event, db):
    status, body = choose(authenticated_event, "archsummoner")
    assert status == 409
    assert (USER, None) not in db.tables["profiles"]
    assert choose(authenticated_event, "made_up")[0] == 404
    assert choose(authenticated_event, 7)[0] == 400
