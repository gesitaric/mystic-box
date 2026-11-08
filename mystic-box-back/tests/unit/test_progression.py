import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from mystic_shared import progression

from get_profile import app as get_profile


def test_level_curve():
    assert progression.level_for_experience(0) == (1, 0)
    assert progression.level_for_experience(99) == (1, 99)
    assert progression.level_for_experience(100) == (2, 0)
    # 100 (1->2) + 130 (2->3) = 230
    assert progression.level_for_experience(229) == (2, 129)
    assert progression.level_for_experience(230) == (3, 0)


def test_level_is_capped():
    level, _ = progression.level_for_experience(10**9)
    assert level == progression.MAX_LEVEL
    assert progression.experience_to_next(progression.MAX_LEVEL) is None


def test_negative_experience_is_level_one():
    assert progression.level_for_experience(-5) == (1, 0)


def test_level_up_reward():
    assert progression.level_up_reward(1, 1) == 0
    assert progression.level_up_reward(1, 2) == 20
    assert progression.level_up_reward(1, 3) == 20 + 30


def test_public_progress():
    assert progression.public_progress(150, wins=2, losses=1) == {
        "level": 2,
        "maxLevel": progression.MAX_LEVEL,
        "experience": 150,
        "levelExperience": 50,
        "nextLevelExperience": 130,
        "wins": 2,
        "losses": 1,
    }


@pytest.fixture()
def profile_client(monkeypatch):
    client = MagicMock()
    # Ascensões (títulos dos capítulos secretos): nenhuma.
    client.query.return_value = {"Items": []}
    monkeypatch.setattr(get_profile, "_client", client)
    monkeypatch.setattr(get_profile, "USER_PROGRESS_TABLE", "progress")
    return client


def test_get_profile_options(apigw_event):
    ret = get_profile.lambda_handler(dict(apigw_event, httpMethod="OPTIONS"), "")
    assert ret["statusCode"] == 200


def test_get_profile_requires_authentication(apigw_event):
    ret = get_profile.lambda_handler(dict(apigw_event, httpMethod="GET"), "")
    assert ret["statusCode"] == 401


def test_get_profile_new_user_is_level_one(authenticated_event, profile_client):
    profile_client.get_item.return_value = {}

    ret = get_profile.lambda_handler(authenticated_event(httpMethod="GET"), "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data["level"] == 1
    assert data["experience"] == 0
    assert data["nextLevelExperience"] == progression.BASE_LEVEL_EXPERIENCE
    key = profile_client.get_item.call_args.kwargs["Key"]
    assert key == {"userId": {"S": "user-123"}}


def test_get_profile_reads_stored_progress(authenticated_event, profile_client):
    profile_client.get_item.return_value = {
        "Item": {
            "userId": {"S": "user-123"},
            "experience": {"N": "230"},
            "wins": {"N": "4"},
            "losses": {"N": "2"},
        }
    }

    data = json.loads(
        get_profile.lambda_handler(authenticated_event(httpMethod="GET"), "")["body"]
    )

    assert data["level"] == 3
    assert data["wins"] == 4
    assert data["losses"] == 2


def test_get_profile_database_error(authenticated_event, profile_client):
    profile_client.get_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError"}}, "GetItem"
    )

    ret = get_profile.lambda_handler(authenticated_event(httpMethod="GET"), "")
    assert ret["statusCode"] == 500
