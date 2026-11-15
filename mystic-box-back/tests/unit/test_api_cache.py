"""Cache do CloudFront na frente da API (`ApiDistribution` no template.yaml)."""

import sys
from pathlib import Path

import pytest

from get_rules import app as get_rules
from get_world import app as get_world

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR / "local"))

import dev_server  # noqa: E402


@pytest.fixture(scope="module")
def template():
    return dev_server.load_template()


def distribution(template):
    return template["Resources"]["ApiDistribution"]["Properties"]["DistributionConfig"]


def public_get_paths(template):
    """Caminhos de GET sem autorizador (rotas públicas)."""
    paths = set()
    for resource in template["Resources"].values():
        if resource.get("Type") != "AWS::Serverless::Function":
            continue
        for event in (resource["Properties"].get("Events") or {}).values():
            props = event.get("Properties", {})
            if event.get("Type") == "Api" and props.get("Method") == "get" and not props.get("Auth"):
                paths.add(props["Path"])
    return paths


def test_only_public_routes_are_cached(template):
    """Rota com login nunca entra no cache: a resposta é de um jogador só."""
    cached = {b["PathPattern"] for b in distribution(template)["CacheBehaviors"]}

    assert cached == {"/rules", "/world"}
    assert cached <= public_get_paths(template)


def test_other_routes_are_not_cached_and_keep_authorization(template):
    default = distribution(template)["DefaultCacheBehavior"]

    # Managed-CachingDisabled e Managed-AllViewerExceptHostHeader.
    assert default["CachePolicyId"] == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    assert default["OriginRequestPolicyId"] == "b689b0a8-53d0-40ab-baf2-68738e2966ac"
    assert {"POST", "GET", "OPTIONS"} <= set(default["AllowedMethods"])


def test_error_responses_are_not_cached(template):
    errors = distribution(template)["CustomErrorResponses"]

    assert {e["ErrorCode"] for e in errors} >= {400, 403, 404, 500, 502, 503, 504}
    assert all(e["ErrorCachingMinTTL"] == 0 for e in errors)
    assert not any("ResponsePagePath" in e for e in errors)


@pytest.mark.parametrize("handler", [get_rules, get_world])
def test_public_routes_send_cache_control(handler, template):
    """O CloudFront guarda a resposta pelo tempo que a Lambda pedir."""
    ret = handler.lambda_handler({"httpMethod": "GET"}, "")
    cache_control = ret["headers"]["Cache-Control"]
    max_age = int(cache_control.split("max-age=")[1])

    policy = template["Resources"]["PublicApiCachePolicy"]["Properties"]["CachePolicyConfig"]
    assert cache_control.startswith("public")
    assert policy["MinTTL"] <= max_age <= policy["MaxTTL"]
