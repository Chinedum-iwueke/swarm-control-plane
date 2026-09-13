from __future__ import annotations

import runpy
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parents[1]


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.charter = {
            "id": "charter-1",
            "agent_id": "agent-1",
            "manifest_digest": "",
            "status": "draft",
        }

    def request(self, method: str, path: str, json: dict | None = None):
        self.calls.append((method, path, json))
        payload: object
        if path == "/v1/agent-governance/charters" and method == "GET":
            payload = []
        elif path == "/v1/agent-governance/charters" and method == "POST":
            self.charter = {
                "id": "charter-1",
                "agent_id": "agent-1",
                "manifest_digest": json["manifest_digest"],
                "status": "draft",
            }
            payload = self.charter
        elif path.endswith("/activate"):
            self.charter["status"] = "active"
            payload = self.charter
        elif path == "/v1/agent-governance/grants" and method == "GET":
            payload = []
        elif path == "/v1/agent-governance/grants":
            payload = {
                "id": f"grant-{json['capability']}",
                **json,
                "status": "active",
            }
        elif path == "/v1/workload-identities" and method == "GET":
            payload = []
        elif path == "/v1/workload-identities":
            payload = {
                "id": "identity-1",
                **json,
                "status": "active",
                "expires_at": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
            }
        elif path.endswith("/bind-credentials"):
            payload = {"identity_id": "identity-1", "bound_credentials": 1}
        else:
            raise AssertionError((method, path, json))

        class Response:
            def raise_for_status(self):
                return self

            def json(self):
                return payload

        return Response()


def test_exec1_observer_profile_is_canonical() -> None:
    module = runpy.run_path(str(ROOT / "scripts/ops004_bootstrap.py"))
    profile = module["PROFILES"]["exec1"]
    assert profile == {
        "package": "exec1-fleet-observer",
        "slug": "exec1-fleet-observer",
        "display_name": "EXEC1 Fleet Observer",
        "machine": "exec1-execution",
    }


def test_exec1_installer_is_valid_and_does_not_enable_execution() -> None:
    installer = ROOT / "systemd/install-exec1-host.sh"
    subprocess.run(["bash", "-n", str(installer)], check=True)
    source = installer.read_text(encoding="utf-8")
    assert 'capital_authority": False' in source
    assert 'order_authority": False' in source
    assert 'execution_runtime_enabled": False' in source
    assert "BYBIT_API" not in source
    assert "BINANCE_API" not in source
    assert "systemctl enable --now invariance-swarm-execution" not in source


def test_observer_governance_binds_exact_package_with_fleet_scope() -> None:
    module = runpy.run_path(str(ROOT / "scripts/ops004_bootstrap.py"))
    client = FakeClient()
    package = {
        "id": "package-1",
        "manifest_digest": "a" * 64,
        "manifest": {
            "role": "Bounded observer",
            "required_capabilities": [
                "fleet-observation",
                "resource-health",
                "service-health",
            ],
            "task_types": ["fleet_observation"],
            "risk_ceiling": 0,
            "repository_profile": {"repositories": []},
        },
    }
    result = module["ensure_governance"](
        client,
        agent={"id": "agent-1", "machine": "exec1-execution", "risk_ceiling": 0},
        package=package,
    )

    assert result["workload_scopes"] == [
        "control:read",
        "fleet:write",
        "heartbeat:write",
        "identity:read",
        "package:read",
        "task:execute",
        "task:lease",
    ]
    grant_payloads = [
        payload
        for method, path, payload in client.calls
        if method == "POST" and path == "/v1/agent-governance/grants"
    ]
    assert {item["capability"] for item in grant_payloads} == set(
        package["manifest"]["required_capabilities"]
    )
    assert all(item["package_id"] == "package-1" for item in grant_payloads)
    assert (
        "POST",
        "/v1/workload-identities/identity-1/bind-credentials",
        {"actor": "founder-operator"},
    ) in client.calls
    assert not any("rotate" in path for _, path, _ in client.calls)
