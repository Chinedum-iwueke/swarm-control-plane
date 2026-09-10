import importlib.util
from pathlib import Path

import httpx

SPEC = importlib.util.spec_from_file_location(
    "alpha002_bootstrap",
    Path(__file__).parents[1] / "scripts" / "alpha002_bootstrap.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def state() -> dict:
    return {
        "agent_id": "11111111-1111-4111-8111-111111111111",
        "charter_id": "22222222-2222-4222-8222-222222222222",
        "package_id": "33333333-3333-4333-8333-333333333333",
    }


def identity() -> dict:
    return {
        "id": "44444444-4444-4444-8444-444444444444",
        **state(),
        "status": "active",
        "scopes": MODULE.WORKLOAD_SCOPES,
    }


def test_missing_workload_identity_is_created_and_credential_is_bound() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, request.content))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == "/v1/workload-identities":
            return httpx.Response(201, json=identity())
        if request.url.path.endswith("/bind-credentials"):
            return httpx.Response(200, json={"bound_credentials": 1})
        raise AssertionError(request.url.path)

    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = MODULE.ensure_workload_identity(
            client, state(), expires_at="2027-09-10T00:00:00+00:00"
        )

    assert result["id"] == identity()["id"]
    assert [item[:2] for item in requests] == [
        ("GET", "/v1/workload-identities"),
        ("POST", "/v1/workload-identities"),
        (
            "POST",
            "/v1/workload-identities/44444444-4444-4444-8444-444444444444/bind-credentials",
        ),
    ]


def test_existing_workload_identity_is_reused_without_rotation() -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[identity()])
        if request.url.path.endswith("/bind-credentials"):
            return httpx.Response(200, json={"bound_credentials": 0})
        raise AssertionError(request.url.path)

    existing = state() | {"workload_identity_id": identity()["id"]}
    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = MODULE.ensure_workload_identity(
            client, existing, expires_at="2027-09-10T00:00:00+00:00"
        )

    assert result["id"] == identity()["id"]
    assert methods == [
        ("GET", "/v1/workload-identities"),
        (
            "POST",
            "/v1/workload-identities/44444444-4444-4444-8444-444444444444/bind-credentials",
        ),
    ]
