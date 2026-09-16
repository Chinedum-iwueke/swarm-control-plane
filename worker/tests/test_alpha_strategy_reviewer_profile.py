import importlib.util
import json
from pathlib import Path

import httpx
import pytest

SPEC = importlib.util.spec_from_file_location(
    "reviewer_profile",
    Path(__file__).parents[1] / "scripts/alpha_strategy_reviewer_profile.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
STATE = {
    "slug": "vm1-alpha-spec-reviewer",
    "agent_id": "agent",
    "package_id": "package",
    "manifest_digest": "a" * 64,
}


def profile():
    return {
        "id": "profile",
        "agent_id": "agent",
        "profile_version": "1.0.0",
        "review_kinds": ["strategy_spec"],
        "capabilities": ["alpha-strategy-review-strategy_spec"],
        "provider": "openai",
        "model_family": "codex",
        "context_group": "alpha-independent-spec-reviewer-v1",
        "registered_by": "founder-operator",
        "status": "active",
        "machine": "vm1-developer",
        "package_id": "package",
        "package_digest": "a" * 64,
    }


@pytest.mark.parametrize("existing", [False, True])
def test_registers_or_reuses_exact_profile_without_review_completion(existing):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[profile()] if existing else [])
        assert request.url.path == "/v1/evaluator-routing/profiles"
        assert json.loads(request.content)["review_kinds"] == ["strategy_spec"]
        return httpx.Response(201, json=profile())

    with httpx.Client(
        base_url="http://test", transport=httpx.MockTransport(handler)
    ) as client:
        assert (
            MODULE.ensure_profile(client, STATE, "spec", "openai", "codex") == profile()
        )
    assert [r.method for r in requests] == (["GET"] if existing else ["GET", "POST"])


@pytest.mark.parametrize(
    "key,value",
    [
        ("package_digest", "b" * 64),
        ("package_id", "other"),
        ("status", "revoked"),
        ("context_group", "producer-context"),
        ("capabilities", ["backtesting"]),
    ],
)
def test_rejects_conflicting_profile_without_rotation(key, value):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json=[{**profile(), key: value}])

    with (
        httpx.Client(
            base_url="http://test", transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(RuntimeError, match="differs"),
    ):
        MODULE.ensure_profile(client, STATE, "spec", "openai", "codex")
