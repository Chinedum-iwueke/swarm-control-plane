from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hermes_mission_control.app import create_app
from hermes_mission_control.config import MissionControlSettings


class FakeControlPlane:
    def __init__(self) -> None:
        self.intake: Any = None
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def dashboard(self) -> dict:
        return {
            "health": {"status": "ok"},
            "tasks": [],
            "agents": [],
            "approvals": [],
            "artifacts": [],
            "control_scopes": [],
        }

    async def create_intake(self, payload) -> dict:
        self.intake = payload
        return {"id": "task-id"}

    async def decide_approval(self, approval_id, action, decision) -> dict:
        return {"id": approval_id, "status": f"{action}d", "reason": decision.reason}

    async def set_pause(self, **kwargs) -> dict:
        return kwargs


def test_static_application_and_safe_status(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        page = client.get("/")
        status = client.get("/api/status")
    assert page.status_code == 200
    assert "Hermes Mission Control" in page.text
    assert 'id="command"' in page.text
    assert 'id="research"' in page.text
    assert 'id="evidence"' in page.text
    assert settings.read_token() not in page.text
    assert status.json()["scope"] == "loopback-only"
    assert fake.closed is True


def test_application_routes_construct_for_supported_python(
    settings: MissionControlSettings,
) -> None:
    app = create_app(settings, control_plane=FakeControlPlane())
    paths = {route.path for route in app.routes}
    assert "/api/intake" in paths
    assert "/api/knowledge/search" in paths


def test_mutations_require_founder_intent_header(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    payload = {
        "kind": "task",
        "project": "swarm-control-plane",
        "title": "Review the next milestone",
        "objective": "Prepare a bounded implementation plan for review.",
        "risk_level": 0,
        "acceptance_criteria": [],
    }
    with TestClient(create_app(settings, control_plane=fake)) as client:
        denied = client.post("/api/intake", json=payload)
        accepted = client.post(
            "/api/intake",
            json=payload,
            headers={"X-Hermes-Intent": "founder-action"},
        )
    assert denied.status_code == 403
    assert accepted.status_code == 200
    assert fake.intake.project == "swarm-control-plane"


def test_unknown_intake_fields_are_rejected(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    payload = {
        "kind": "task",
        "project": "swarm-control-plane",
        "title": "Unsafe request",
        "objective": "Attempt to add an arbitrary command field.",
        "risk_level": 0,
        "acceptance_criteria": [],
        "command": "bash -c dangerous",
    }
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.post(
            "/api/intake",
            json=payload,
            headers={"X-Hermes-Intent": "founder-action"},
        )
    assert response.status_code == 422
