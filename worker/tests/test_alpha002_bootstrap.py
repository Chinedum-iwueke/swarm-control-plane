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


def test_api_error_reports_route_and_detail_without_request_payload() -> None:
    secret = "signed-package-secret-that-must-not-be-printed"

    def handler(request: httpx.Request) -> httpx.Response:
        assert secret.encode() in request.content
        return httpx.Response(
            422,
            json={"detail": "capability name does not match the safe-name contract"},
        )

    with httpx.Client(
        base_url="http://control-plane.test",
        transport=httpx.MockTransport(handler),
    ) as client, pytest.raises(RuntimeError) as failure:
        MODULE.call(
            client,
            "POST",
            "/v1/packages",
            {"signature": secret},
        )

    message = str(failure.value)
    assert "POST /v1/packages failed (422)" in message
    assert "safe-name contract" in message
    assert secret not in message


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
                        "deployment": {
                            "id": "deployment",
                            "agent_id": agent["id"],
                            "package_id": state()["package_id"],
                            "is_active": True,
                        },
                        "package": {"id": state()["package_id"]},
                    }
                ],
                "/v1/agent-governance/charters": [],
                "/v1/agent-governance/grants": [],
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


def test_existing_state_requires_explicit_package_rotation(
    tmp_path, monkeypatch
) -> None:
    package_name = "vm1-alpha-strategy-engineer"
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
        "risk_ceiling": manifest.risk_ceiling,
        "is_enabled": True,
    }
    old_package_id = "55555555-5555-4555-8555-555555555555"
    new_package_id = "66666666-6666-4666-8666-666666666666"
    old_deployment_id = "77777777-7777-4777-8777-777777777777"
    new_deployment_id = "88888888-8888-4888-8888-888888888888"
    requests = []

    def handler(request):
        path = request.url.path
        requests.append((request.method, path))
        if request.method == "GET":
            values = {
                "/v1/packages": [
                    {
                        "id": old_package_id,
                        "name": package_name,
                        "version": "1.0.0",
                        "manifest_digest": "0" * 64,
                    }
                ],
                "/v1/agents": [agent],
                "/v1/packages/deployments": [
                    {
                        "deployment": {
                            "id": old_deployment_id,
                            "agent_id": agent["id"],
                            "package_id": old_package_id,
                            "is_active": True,
                        },
                        "package": {"id": old_package_id},
                    }
                ],
                "/v1/agent-governance/charters": [],
                "/v1/agent-governance/grants": [
                    {
                        "id": capability,
                        "agent_id": agent["id"],
                        "charter_id": state()["charter_id"],
                        "package_id": new_package_id,
                        "capability": capability,
                        "status": "active",
                    }
                    for capability in manifest.required_capabilities
                ],
                "/v1/workload-identities": [],
            }
            return httpx.Response(200, json=values[path])
        payload = json.loads(request.content or b"{}")
        if path == "/v1/packages":
            return httpx.Response(
                201,
                json={
                    "id": new_package_id,
                    "name": package_name,
                    "version": manifest.version,
                    "manifest_digest": manifest_digest,
                },
            )
        if path == "/v1/packages/deployments":
            assert payload["package_id"] == new_package_id
            return httpx.Response(
                201,
                json={
                    "id": new_deployment_id,
                    "agent_id": agent["id"],
                    "package_id": new_package_id,
                    "is_active": True,
                },
            )
        if path == f"/v1/packages/deployments/{old_deployment_id}/revoke":
            return httpx.Response(200, json={"id": old_deployment_id})
        if path == "/v1/agent-governance/charters":
            return httpx.Response(201, json={"id": state()["charter_id"]})
        if path.endswith("/activate"):
            return httpx.Response(200, json={"id": state()["charter_id"]})
        if path == "/v1/agent-governance/grants":
            return httpx.Response(201, json={"id": payload["capability"]})
        if path == "/v1/workload-identities":
            assert payload["version"] == "1.0.1"
            created = identity() | {"package_id": new_package_id}
            return httpx.Response(201, json=created)
        if path.endswith(("/bind-credentials", "/credentials/finalize")):
            return httpx.Response(200, json={"status": "ok"})
        if path.endswith("/credentials/rotate"):
            return httpx.Response(201, json={"token": "rotated-secret"})
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
    state_file.write_text(
        json.dumps(
            {
                **state(),
                "slug": package_name,
                "package_id": old_package_id,
                "deployment_id": old_deployment_id,
                "manifest_digest": "0" * 64,
                "source_commit": "a" * 40,
            }
        )
    )
    env_file.write_text("SWARM_AGENT_TOKEN=old-secret\n")
    state_file.chmod(0o600)
    env_file.chmod(0o600)
    base_argv = [
        "bootstrap",
        "--package",
        package_name,
        "--state",
        str(state_file),
        "--environment",
        str(env_file),
        "--source-commit",
        "b" * 40,
    ]
    monkeypatch.setattr(sys, "argv", base_argv)
    with pytest.raises(RuntimeError, match="explicit package/credential rotation"):
        MODULE.main()
    assert requests == []

    monkeypatch.setattr(
        sys,
        "argv",
        [*base_argv, "--rotate-package"],
    )

    assert MODULE.main() == 0
    rotated = json.loads(state_file.read_text())
    assert rotated["package_id"] == new_package_id
    assert rotated["deployment_id"] == new_deployment_id
    assert rotated["manifest_digest"] == manifest_digest
    assert rotated["source_commit"] == "b" * 40
    assert rotated["workload_identity_version"] == "1.0.1"
    assert "SWARM_AGENT_TOKEN=rotated-secret" in env_file.read_text()
    assert ("POST", "/v1/agent-governance/grants") not in requests
    deploy_index = requests.index(("POST", "/v1/packages/deployments"))
    revoke_index = requests.index(
        ("POST", f"/v1/packages/deployments/{old_deployment_id}/revoke")
    )
    assert deploy_index < revoke_index
