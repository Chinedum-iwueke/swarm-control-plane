import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

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


@pytest.mark.parametrize("recover", [False, True])
def test_partial_registration_requires_explicit_scoped_recovery(
    tmp_path, monkeypatch, recover
):
    package_name = "vm1-alpha-research-executor-capacity-2"
    manifest = MODULE.load_role_package(
        MODULE.ROOT / "role-packages" / package_name / "manifest.yaml",
        MODULE.ROOT / "workflows",
    ).manifest
    manifest_digest = MODULE.hashlib.sha256(
        MODULE.canonical_manifest(manifest)
    ).hexdigest()
    agent = {
        "id": state()["agent_id"],
        "slug": package_name,
        "machine": "vm1-developer",
        "role": manifest.role,
        "capabilities": manifest.required_capabilities,
        "risk_ceiling": 0,
        "is_enabled": True,
    }
    requests = []

    def handler(request):
        path = request.url.path
        requests.append((request.method, path))
        if request.method == "GET":
            values = {
                "/v1/packages": [
                    {
                        "id": state()["package_id"],
                        "name": package_name,
                        "version": manifest.version,
                        "manifest_digest": manifest_digest,
                    }
                ],
                "/v1/agents": [agent],
                "/v1/packages/deployments": [
                    {
                        "id": "deployment",
                        "agent_id": agent["id"],
                        "package_id": state()["package_id"],
                        "is_active": True,
                    }
                ],
                "/v1/agent-governance/charters": [],
                "/v1/workload-identities": [],
            }
            return httpx.Response(200, json=values[path])
        payload = json.loads(request.content)
        if path == "/v1/agent-governance/charters":
            assert package_name in payload["manifest"]["responsibilities"][0]
            assert payload["manifest_digest"] == MODULE.digest(payload["manifest"])
            return httpx.Response(201, json={"id": state()["charter_id"]})
        if path.endswith("/activate"):
            return httpx.Response(200, json={"id": state()["charter_id"]})
        if path == "/v1/agent-governance/grants":
            return httpx.Response(201, json={"id": payload["capability"]})
        if path == "/v1/workload-identities":
            return httpx.Response(201, json=identity())
        if path.endswith(("/bind-credentials", "/credentials/finalize")):
            return httpx.Response(200, json={"status": "ok"})
        if path.endswith("/credentials/rotate"):
            assert payload == {"actor": "founder-operator", "overlap_seconds": 30}
            return httpx.Response(201, json={"token": "recovered-secret"})
        raise AssertionError(path)

    client_type = httpx.Client
    monkeypatch.setattr(
        MODULE.httpx,
        "Client",
        lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setenv("SWARM_API_URL", "http://control-plane.test")
    monkeypatch.setenv("SWARM_ORCHESTRATOR_TOKEN", "operator")
    monkeypatch.setenv("SWARM_PACKAGE_SIGNING_SECRET", "signing")
    state_file, env_file = tmp_path / "state.json", tmp_path / "executor.env"
    argv = [
        "bootstrap",
        "--package",
        package_name,
        "--state",
        str(state_file),
        "--environment",
        str(env_file),
        "--source-commit",
        "a" * 40,
    ]
    if recover:
        argv.append("--recover-registration")
    monkeypatch.setattr(sys, "argv", argv)
    if not recover:
        with pytest.raises(RuntimeError, match="refusing implicit rotation"):
            MODULE.main()
        assert not state_file.exists() and not env_file.exists()
        assert all(method == "GET" for method, _ in requests)
        return
    assert MODULE.main() == 0
    assert "SWARM_AGENT_TOKEN=recovered-secret" in env_file.read_text()
    assert env_file.stat().st_mode & 0o777 == 0o600
    assert json.loads(state_file.read_text())["agent_id"] == agent["id"]
    assert ("POST", "/v1/agents") not in requests
    assert ("POST", "/v1/packages/deployments") not in requests
    assert requests[-1][1].endswith("/credentials/finalize")
