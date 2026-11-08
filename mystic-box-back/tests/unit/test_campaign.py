import json

from mystic_shared import campaign
from mystic_shared.cards import get_character
from mystic_shared.lore import REGIONS, STORIES

from get_campaign import app as get_campaign
from tests.unit.fake_dynamo import FakeDynamo


def test_every_region_with_champions_has_a_campaign():
    with_champions = {lore["region"] for lore in STORIES.values()}
    assert set(campaign.CAMPAIGN) == with_champions
    assert set(campaign.CAMPAIGN) <= {region["id"] for region in REGIONS}


def test_stages_are_well_formed():
    for region_id, region in campaign.CAMPAIGN.items():
        assert len(region["stages"]) == campaign.STAGES_PER_REGION, region_id
        assert region["epilogue"].strip()
        for stage in region["stages"]:
            assert stage["name"] and stage["intro"]
            assert len(set(stage["enemies"])) == 3, (region_id, stage["name"])
            assert all(get_character(name) for name in stage["enemies"])


def test_stage_unlocks_in_order():
    campaign.check_stage("nocthaven", 1, 0)
    campaign.check_stage("nocthaven", 3, 2)
    for args in (("nocthaven", 2, 0), ("nocthaven", 4, 3), ("riftheart", 1, 0)):
        try:
            campaign.check_stage(*args)
        except campaign.CampaignError:
            continue
        raise AssertionError(args)


def test_stage_setup_scales_with_player_level():
    setup = campaign.stage_setup("nocthaven", 3, 10)
    assert setup["boss"] is True
    assert setup["enemyLevel"] == 10 + campaign.STAGE_RULES[2]["levelOffset"]
    assert [c["file_name"] for c in setup["enemies"]] == ["malachar.jfif", "mortis.jfif",
                                                          "ravenna.png"]


def test_public_campaign_hides_epilogue_until_the_boss_falls():
    regions = {r["region"]: r for r in campaign.public_campaign({"nocthaven": 3,
                                                                  "hrimvald": 1}, 5)}
    assert regions["nocthaven"]["complete"] is True
    assert regions["nocthaven"]["epilogue"] == campaign.epilogue("nocthaven")
    assert regions["hrimvald"]["epilogue"] is None
    stages = regions["hrimvald"]["stages"]
    assert [s["cleared"] for s in stages] == [True, False, False]
    assert [s["unlocked"] for s in stages] == [True, True, False]


def test_get_campaign_endpoint(apigw_event, authenticated_event, monkeypatch):
    fake = FakeDynamo({"regions": ("userId", None), "progress": ("userId", None)})
    fake.tables["regions"][("user-123", None)] = {"userId": {"S": "user-123"},
                                                  "stage_cinderpeak": {"N": "2"}}
    monkeypatch.setattr(get_campaign, "_client", fake)
    monkeypatch.setattr(get_campaign, "REGION_PROGRESS_TABLE", "regions")
    monkeypatch.setattr(get_campaign, "USER_PROGRESS_TABLE", "progress")

    assert get_campaign.lambda_handler(apigw_event, "")["statusCode"] == 401
    ret = get_campaign.lambda_handler(authenticated_event(httpMethod="GET"), "")
    body = json.loads(ret["body"])
    cinderpeak = next(r for r in body["regions"] if r["region"] == "cinderpeak")
    assert ret["statusCode"] == 200
    assert cinderpeak["cleared"] == 2
    assert body["level"] == 1
