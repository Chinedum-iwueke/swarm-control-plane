from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from hermes_mission_control.app import create_app
from hermes_mission_control.config import MissionControlSettings


class FakeControlPlane:
    def __init__(self) -> None:
        self.intake: Any = None
        self.bundle: Any = None
        self.ingestion: Any = None
        self.reconciliation: Any = None
        self.closed = False
        self.memory_sync_requested = False
        self.dossier_requested: str | None = None
        self.lifecycle_requested: str | None = None
        self.surveillance_requested: str | None = None
        self.graph_requested = False
        self.conversation_turns: list[tuple[str, str]] = []
        self.research_cycle_decision: tuple[str, str, str, str] | None = None

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

    async def conversations(self) -> list[dict]:
        return []

    async def conversation_workspace(self, conversation_id: str) -> dict:
        return {
            "conversation": {"id": conversation_id, "revision": 2},
            "events": [],
            "proposals": [],
            "tasks": [],
            "approvals": [],
            "artifacts": [],
        }

    async def create_conversation(self, title: str, message: str) -> dict:
        self.conversation_turns.append((title, message))
        return {"conversation": {"id": "conversation-id", "revision": 1}}

    async def add_conversation_turn(self, conversation_id: str, message: str) -> dict:
        self.conversation_turns.append((conversation_id, message))
        return {"conversation": {"id": conversation_id, "revision": 2}}

    async def transition_conversation(
        self, conversation_id: str, action: str, reason: str
    ) -> dict:
        return {"id": conversation_id, "status": action, "reason": reason}

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

    async def create_scientific_ingestion(self, payload) -> dict:
        self.ingestion = payload
        return {
            "id": "ingestion-id",
            "status": "quarantined",
            "published_object_ids": [],
        }

    async def process_scientific_ingestion(self, job_id) -> dict:
        assert job_id == "ingestion-id"
        return {
            "id": job_id,
            "status": "published",
            "published_object_ids": ["source", "edition", "artifact", "passage"],
        }

    async def reconcile_corpus(self, payload) -> dict:
        self.reconciliation = payload
        return {"id": "sync-id"}

    async def rebuild_corpus_projections(self, project) -> dict:
        return {"evidence": {"project": project, "status": "rebuilt"}}

    async def propose_research_memory_sync(self) -> dict:
        self.memory_sync_requested = True
        return {"id": "memory-proposal-id", "status": "proposed"}

    async def decide_research_cycle(
        self, cycle_id, expected_question_digest, decision, rationale
    ) -> dict:
        self.research_cycle_decision = (
            cycle_id,
            expected_question_digest,
            decision,
            rationale,
        )
        return {"id": cycle_id, "status": "awaiting_brief"}

    async def get_evidence_dossier(self, dossier_id: str) -> dict:
        self.dossier_requested = dossier_id
        return {"id": dossier_id, "dossier_key": "RI004-PILOT"}

    async def replay_evidence_dossier(self, dossier_id: str) -> dict:
        self.dossier_requested = dossier_id
        return {"exact_replay": True, "impacts": []}

    async def get_evidence_lifecycle(self, object_id: str) -> dict:
        self.lifecycle_requested = object_id
        return {"state": {"object_id": object_id, "state": "retracted"}}

    async def transition_evidence_lifecycle(
        self, object_id: str, payload: dict
    ) -> dict:
        self.lifecycle_requested = object_id
        return {"state": {"object_id": object_id, "state": payload["action"]}}

    async def replay_surveillance_candidate(self, publication_id: str) -> dict:
        self.surveillance_requested = publication_id
        return {"publication_id": publication_id, "exact_replay": True}

    async def knowledge_graph(self, *, limit: int = 100) -> dict:
        self.graph_requested = True
        return {
            "projection_version": "knowledge-graph-v1.0.0",
            "corpus_digest": "a" * 64,
            "query_digest": "b" * 64,
            "nodes": [
                {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "label": "A supported claim",
                    "object_type": "claim",
                    "project": "systematic-research",
                    "access_class": "internal",
                    "content_digest": "c" * 64,
                }
            ],
            "edges": [],
            "paths": [],
            "truncated": False,
        }

    async def query_knowledge_graph(self, payload: dict) -> dict:
        self.graph_query = payload
        return await self.knowledge_graph(limit=payload["max_nodes"])

    async def research_retrieval(self, payload) -> dict:
        return {
            "corpus_digest": "a" * 64,
            "confidence": 0.0,
            "abstained": True,
            "hits": [],
            "timings_ms": {},
        }

    async def research_context_pack(self, payload) -> dict:
        raise AssertionError("An abstained query must not build a context pack")

    async def replay_research_citation(self, object_id: str) -> dict:
        return {"object_id": object_id, "exact_replay": True}


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
    assert 'role="tablist" aria-label="Research workspace mode"' in page.text
    assert 'id="research-panel-ask"' in page.text
    assert 'id="research-panel-explore"' in page.text
    assert 'id="research-panel-library"' in page.text
    assert 'id="research-context-items"' in page.text
    assert settings.read_token() not in page.text
    assert status.json()["scope"] == "loopback-only"
    assert fake.closed is True


def test_new_thread_dialog_cancel_bypasses_required_field_validation(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        html = client.get("/").text
        script = client.get("/static/app.js").text

    assert (
        '<button type="button" class="secondary" data-close-dialog>Cancel</button>'
        in html
    )
    assert 'document.querySelectorAll("[data-close-dialog]")' in script


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
    assert "/api/research/evidence/{object_id}/lifecycle" in paths
    assert "/api/research/surveillance/{publication_id}/replay" in paths
    assert "/api/research/copilot/questions" in paths
    assert "/api/research/copilot/citations/{object_id}" in paths
    assert "/api/knowledge/graph/query" in paths


def test_graph_explorer_uses_canonical_control_plane_projection(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get("/api/knowledge/graph")
    assert response.status_code == 200
    assert response.json()["projection_version"] == "knowledge-graph-v1.0.0"
    assert response.json()["nodes"][0]["object_type"] == "claim"
    assert fake.graph_requested is True


def test_graph_explorer_forwards_only_typed_bounded_query(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    root_id = "11111111-1111-4111-8111-111111111111"
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.post(
            "/api/knowledge/graph/query",
            json={
                "root_ids": [root_id],
                "mode": "neighborhood",
                "predicates": ["supports", "contradicts"],
                "direction": "both",
                "max_depth": 2,
                "max_nodes": 80,
                "project": "systematic-research",
            },
        )
    assert response.status_code == 200
    assert fake.graph_query["root_ids"] == [root_id]
    assert fake.graph_query["max_nodes"] == 80
    assert "command" not in fake.graph_query


def test_graph_explorer_rejects_unbounded_or_executable_input(
    settings: MissionControlSettings,
) -> None:
    root_id = "11111111-1111-4111-8111-111111111111"
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        response = client.post(
            "/api/knowledge/graph/query",
            json={"root_ids": [root_id], "max_nodes": 500, "command": "shell"},
        )
    assert response.status_code == 422


def test_research_copilot_abstention_is_bounded_and_read_only(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.post(
            "/api/research/copilot/questions",
            json={"question": "What is absent from the corpus?", "project": None},
        )
    assert response.status_code == 200
    assert response.json()["confidence"] == "insufficient_evidence"
    assert response.json()["sources"] == []


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


def test_conversation_turns_require_intent_and_reuse_thread(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    headers = {"X-Hermes-Intent": "founder-action"}
    with TestClient(create_app(settings, control_plane=fake)) as client:
        denied = client.post(
            "/api/conversations",
            json={"title": "Research thread", "message": "Test momentum."},
        )
        created = client.post(
            "/api/conversations",
            headers=headers,
            json={"title": "Research thread", "message": "Test momentum."},
        )
        continued = client.post(
            "/api/conversations/conversation-id/turns",
            headers=headers,
            json={"message": "Use January 2022."},
        )

    assert denied.status_code == 403
    assert created.status_code == 200
    assert continued.json()["conversation"]["revision"] == 2
    assert fake.conversation_turns == [
        ("Research thread", "Test momentum."),
        ("conversation-id", "Use January 2022."),
    ]


def test_conversation_workspace_is_read_only_and_canonical(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get("/api/conversations/conversation-id/workspace")

    assert response.status_code == 200
    assert response.json()["conversation"] == {
        "id": "conversation-id",
        "revision": 2,
    }


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


def test_research_upload_is_canonical_and_reconciled(
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
    assert fake.ingestion["project"] == "systematic-research"
    assert fake.ingestion["source"]["title"] == "A bounded research paper"
    assert fake.reconciliation["items"][0]["disposition"] == "canonical"
    assert response.json()["passages"] == 1
