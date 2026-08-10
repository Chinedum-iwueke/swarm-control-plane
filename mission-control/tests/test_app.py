from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hermes_mission_control.app import create_app
from hermes_mission_control.config import MissionControlSettings


class FakeControlPlane:
    def __init__(self) -> None:
        self.intake: Any = None
        self.bundle: Any = None
        self.closed = False
        self.memory_sync_requested = False
        self.dossier_requested: str | None = None
        self.surveillance_requested: str | None = None

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
            "package_deployments": [],
            "proposals": [],
        }

    async def create_intake(self, payload) -> dict:
        self.intake = payload
        return {"id": "task-id"}

    async def decide_approval(self, approval_id, action, decision) -> dict:
        return {"id": approval_id, "status": f"{action}d", "reason": decision.reason}

    async def set_pause(self, **kwargs) -> dict:
        return kwargs

    async def decide_proposal(self, proposal_id, action, decision) -> dict:
        return {
            "id": proposal_id,
            "status": action,
            "reason": decision.reason,
        }

    async def register_research_bundle(self, payload) -> dict:
        self.bundle = payload
        return {
            "document": {"id": "document-id"},
            "chunk_count": len(payload["chunks"]),
        }

    async def research_document_by_digest(self, content_digest):
        return None

    async def propose_research_memory_sync(self) -> dict:
        self.memory_sync_requested = True
        return {"id": "memory-proposal-id", "status": "proposed"}

    async def get_evidence_dossier(self, dossier_id: str) -> dict:
        self.dossier_requested = dossier_id
        return {"id": dossier_id, "dossier_key": "RI004-PILOT"}

    async def replay_evidence_dossier(self, dossier_id: str) -> dict:
        self.dossier_requested = dossier_id
        return {"exact_replay": True, "impacts": []}

    async def replay_surveillance_candidate(self, publication_id: str) -> dict:
        self.surveillance_requested = publication_id
        return {"publication_id": publication_id, "exact_replay": True}


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
    assert "/api/proposals/{proposal_id}/{action}" in paths
    assert "/api/knowledge/search" in paths
    assert "/api/research/sources/upload" in paths
    assert "/api/research/memory-sync/proposals" in paths
    assert "/api/research/dossiers/{dossier_id}" in paths
    assert "/api/research/dossiers/{dossier_id}/replay" in paths
    assert "/api/research/surveillance/{publication_id}/replay" in paths


def test_dossier_inspection_and_replay_are_read_only(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        dossier = client.get("/api/research/dossiers/dossier-id")
        replay = client.get("/api/research/dossiers/dossier-id/replay")
    assert dossier.json()["dossier_key"] == "RI004-PILOT"
    assert replay.json() == {"exact_replay": True, "impacts": []}
    assert fake.dossier_requested == "dossier-id"


def test_surveillance_provenance_replay_is_read_only(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        replay = client.get("/api/research/surveillance/publication-id/replay")
    assert replay.json()["exact_replay"] is True
    assert fake.surveillance_requested == "publication-id"


def test_memory_sync_requires_founder_intent_and_creates_proposal(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        denied = client.post("/api/research/memory-sync/proposals")
        accepted = client.post(
            "/api/research/memory-sync/proposals",
            headers={"X-Hermes-Intent": "founder-action"},
        )
    assert denied.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "proposed"
    assert fake.memory_sync_requested is True


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


def test_research_upload_is_atomic_and_citation_preserving(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.post(
            "/api/research/sources/upload",
            headers={"X-Hermes-Intent": "founder-action"},
            files={"file": ("paper.txt", b"first line\nsecond line", "text/plain")},
            data={
                "title": "A bounded research paper",
                "domain": "systematic-research",
                "document_type": "paper",
                "evidence_type": "empirical_evidence",
            },
        )
    assert response.status_code == 200
    assert fake.bundle is not None
    assert fake.bundle["document"]["metadata"]["domains"] == ["systematic-research"]
    assert fake.bundle["chunks"][0]["line_start"] == 1
    assert fake.bundle["chunks"][0]["line_end"] == 2
