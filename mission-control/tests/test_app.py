from __future__ import annotations

from pathlib import Path
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
        self.approval_decision: Any = None
        self.approval_resend: tuple[str, str] | None = None
        self.codex_auth_retry: tuple[str, dict] | None = None
        self.venue_event_query: dict | None = None
        self.evidence_version = "1"

    async def close(self) -> None:
        self.closed = True

    async def dashboard(self, *, refresh: bool = False) -> dict:
        return {
            "health": {"status": "ok"},
            "tasks": [],
            "agents": [],
            "approvals": [],
            "artifacts": [],
            "control_scopes": [],
            "package_deployments": [],
            "proposals": [],
            "fleet_health": {"machines": []},
            "execution_telemetry": {"venues": []},
        }

    async def agent_tasks(
        self, agent_id: str, *, offset: int = 0, limit: int = 25
    ) -> list[dict]:
        return []

    async def venue_event_history(
        self, *, environment=None, venue=None, replay_id=None
    ) -> dict:
        self.venue_event_query = {
            "environment": environment,
            "venue": venue,
            "replay_id": replay_id,
        }
        return {
            "schema_version": "mission-control-venue-event-history-v1",
            "events": [],
            "counts": {"events": 0},
            "replay_coverage": [],
            "claim_boundary": "Immutable EXEC-011 event evidence only.",
        }

    async def task_detail(self, task_id: str) -> dict:
        return {"task": {"id": task_id, "input_contract": {"full": True}}, "events": []}

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
        self.approval_decision = decision
        return {"id": approval_id, "status": f"{action}d", "reason": decision.reason}

    async def resend_approval(self, task_id: str, reason: str) -> dict:
        self.approval_resend = (task_id, reason)
        return {"task": {"id": task_id, "status": "pending_approval"}}

    async def set_pause(self, **kwargs) -> dict:
        return kwargs

    async def retry_codex_auth(self, recovery_id, payload) -> dict:
        self.codex_auth_retry = (recovery_id, payload)
        return {"id": recovery_id, "state": "expired"}

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

    async def knowledge_catalog(self, *, limit: int = 500) -> dict:
        return {"items": [], "count": 0}

    async def query_knowledge_graph(self, payload: dict) -> dict:
        self.graph_query = payload
        return await self.knowledge_graph(limit=payload["max_nodes"])

    async def research_evidence_object(self, object_id: str) -> dict:
        if object_id != "11111111-1111-4111-8111-111111111111":
            raise AssertionError(f"unexpected evidence object {object_id}")
        return self._evidence_object(object_id, "source")

    async def research_evidence_lineage(self, object_id: str) -> dict:
        descendants = {
            "11111111-1111-4111-8111-111111111111": [
                self._evidence_object(
                    "22222222-2222-4222-8222-222222222222", "edition"
                )
            ],
            "22222222-2222-4222-8222-222222222222": [
                self._evidence_object(
                    "33333333-3333-4333-8333-333333333333", "artifact"
                )
            ],
            "33333333-3333-4333-8333-333333333333": [
                self._evidence_object(
                    "44444444-4444-4444-8444-444444444444",
                    "scientific_object",
                    page=1,
                    line_start=1,
                    content="First canonical line.\nSecond canonical line.",
                ),
                self._evidence_object(
                    "55555555-5555-4555-8555-555555555555",
                    "scientific_object",
                    page=2,
                    line_start=3,
                    content="Third canonical line.",
                ),
            ],
        }.get(object_id, [])
        return {"object": {}, "ancestors": [], "descendants": descendants}

    def _evidence_object(
        self,
        object_id: str,
        object_type: str,
        *,
        page: int = 1,
        line_start: int = 1,
        content: str = "",
    ) -> dict:
        payloads = {
            "source": {
                "kind": "source",
                "title": "Canonical Research Note",
                "origin": "research-inbox",
                "rights": "internal",
                "acquired_at": "2026-10-22T00:00:00Z",
            },
            "edition": {"kind": "edition"},
            "artifact": {"kind": "artifact", "media_type": "application/pdf"},
            "scientific_object": {
                "kind": "scientific_object",
                "scientific_type": "paragraph",
                "coordinates": {
                    "page": page,
                    "line_start": line_start,
                    "line_end": line_start + max(len(content.splitlines()) - 1, 0),
                },
                "extraction_method": "pypdf-heldout",
                "extraction_confidence": 0.98,
                "content_text": content,
            },
        }
        return {
            "object_id": object_id,
            "object_type": object_type,
            "content_version": self.evidence_version,
            "content_digest": object_id.replace("-", "")[:32] * 2,
            "project": "systematic-research",
            "access_class": "internal",
            "created_at": "2026-10-22T00:00:00Z",
            "payload": payloads[object_type],
        }

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
        script = client.get("/static/app.js")
        styles = client.get("/static/styles.css")
        logo = client.get("/static/brand/logo-primary.svg")
        font = client.get("/static/fonts/ibm-plex-sans.woff2")
        status = client.get("/api/status")
    assert page.status_code == 200
    assert "Hermes Mission Control" in page.text
    assert 'id="command"' in page.text
    assert 'id="workflows"' in page.text
    assert 'id="workflow-list"' in page.text
    assert 'id="research"' in page.text
    assert 'id="execution"' in page.text
    assert 'id="execution-environments"' in page.text
    assert 'id="execution-overview-status"' in page.text
    assert 'id="command-venue-summary"' in page.text
    assert 'id="command-venues"' in page.text
    assert 'id="evidence"' in page.text
    assert "/static/brand/logo-primary.svg" in page.text
    assert '"Instrument Serif"' in styles.text
    assert '"IBM Plex Sans"' in styles.text
    assert logo.status_code == 200 and 'viewBox="0 0 3335 1025"' in logo.text
    assert font.status_code == 200 and font.headers["content-type"] == "font/woff2"
    assert 'role="tablist" aria-label="Research workspace mode"' in page.text
    assert 'id="research-panel-ask"' in page.text
    assert 'id="research-panel-explore"' in page.text
    assert "renderWorkflowFlow" in script.text
    assert "loadWorkflows" in script.text
    assert "/api/workflows" in script.text
    assert 'id="research-panel-library"' in page.text
    assert 'id="research-context-items"' in page.text
    assert 'id="alpha-founder-ideas"' in page.text
    assert "founder_ideas" in script.text
    assert settings.read_token() not in page.text
    assert page.headers["cache-control"] == "no-store"
    assert script.headers["cache-control"] == "no-store"
    assert status.json()["scope"] == "loopback-only"
    assert fake.closed is True


def test_dashboard_refresh_preserves_research_scroll_position(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        script = client.get("/static/app.js").text

    assert "function navigate(view, { resetScroll = true } = {})" in script
    assert 'if (resetScroll) window.scrollTo({ top: 0, behavior: "smooth" });' in script
    assert "navigate(state.activeView, { resetScroll: false });" in script


def test_investor_walkthrough_api_discloses_unavailable_canonical_steps(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get("/api/investor-walkthrough")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "mission-control-investor-walkthrough-v1"
    assert payload["status"] == "incomplete"
    assert payload["total_steps"] == 5
    assert fake.venue_event_query == {
        "environment": "demo",
        "venue": "bybit",
        "replay_id": None,
    }


def test_investor_walkthrough_journal_binds_current_projection(
    settings: MissionControlSettings,
) -> None:
    with TestClient(
        create_app(settings, control_plane=FakeControlPlane())
    ) as client:
        projection = client.get("/api/investor-walkthrough").json()
        stale = client.post(
            "/api/investor-walkthrough/sessions",
            json={
                "walkthrough_digest": "f" * 64,
                "ready_steps": projection["ready_steps"],
                "total_steps": 5,
            },
        )
        started = client.post(
            "/api/investor-walkthrough/sessions",
            json={
                "walkthrough_digest": projection["walkthrough_digest"],
                "ready_steps": projection["ready_steps"],
                "total_steps": 5,
            },
        )
        session_id = started.json()["id"]
        observed = client.post(
            f"/api/investor-walkthrough/sessions/{session_id}/observations",
            json={
                "step_id": "workflow",
                "kind": "question",
                "elapsed_ms": 500,
                "note": "Which record proves this workflow is current?",
            },
        )
        finished = client.post(
            f"/api/investor-walkthrough/sessions/{session_id}/finish",
            json={
                "status": "completed",
                "elapsed_ms": 900,
                "summary": "Unavailable records were disclosed.",
            },
        )
        sessions = client.get("/api/investor-walkthrough/sessions").json()

    assert stale.status_code == 409
    assert started.status_code == 200
    assert observed.json()["kind"] == "question"
    assert finished.json()["status"] == "completed"
    assert sessions["sessions"][0]["id"] == session_id


def test_dashboard_reports_local_mission_control_presence(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        dashboard = client.get("/api/dashboard").json()

    assert dashboard["mission_control"]["machine"] == "mac-founder-control"
    assert dashboard["mission_control"]["presence"] == "online"
    assert dashboard["mission_control"]["observed_at"]
    assert dashboard["provenance"]["sources"]["mission_control"] == {
        "source_key": "mission_control",
        "source_identity": "mission-control/local-process",
        "fact_class": "derived",
        "freshness": "current",
        "freshness_threshold_seconds": 45,
        "source_timestamp": dashboard["mission_control"]["observed_at"],
        "reason": "locally_observed_process",
    }


def test_autonomy_drain_control_requires_founder_intent(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    payload = {
        "scope_type": "workflow",
        "scope_key": "autonomous-research",
        "reason": "Drain while the local authoring runtime is maintained.",
    }
    with TestClient(create_app(settings, control_plane=fake)) as client:
        script = client.get("/static/app.js").text
        denied = client.post("/api/control/pause", json=payload)
        accepted = client.post(
            "/api/control/pause",
            headers={"X-Hermes-Intent": "founder-action"},
            json=payload,
        )

    assert "Drain paused: no new work starts; active work may finish." in script
    assert denied.status_code == 403
    assert accepted.status_code == 200
    assert accepted.json() == {
        "paused": True,
        "scope_type": "workflow",
        "scope_key": "autonomous-research",
        "reason": payload["reason"],
    }


def test_task_detail_is_loaded_on_demand(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        response = client.get("/api/tasks/task-id")

    assert response.status_code == 200
    assert response.json()["task"]["input_contract"] == {"full": True}


def test_execution_workspace_is_environment_explicit_and_digest_safe(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        html = client.get("/").text
        script = client.get("/static/app.js").text

    for environment in ("shadow", "demo", "live"):
        assert f'data-execution-environment="{environment}"' in html
    assert "renderExecution" in script
    assert "machineInventory" in script
    assert "exec2" in script
    assert 'return agent.presence || agent.status || "offline"' in script
    assert "receipt_digest" in script
    assert "projection_digest" in script
    assert "api_key" not in html


def test_execution_event_history_proxy_preserves_bounded_filters(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get(
            "/api/execution/events",
            params={"environment": "demo", "venue": "bybit", "replay_id": "r-1"},
        )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "mission-control-venue-event-history-v1"
    assert fake.venue_event_query == {
        "environment": "demo",
        "venue": "bybit",
        "replay_id": "r-1",
    }


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


def test_codex_auth_retry_requires_founder_intent_and_preserves_incident(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    payload = {"reason": "Founder requested a replacement device code."}
    with TestClient(create_app(settings, control_plane=fake)) as client:
        denied = client.post(
            "/api/codex-auth/recoveries/recovery-id/retry", json=payload
        )
        accepted = client.post(
            "/api/codex-auth/recoveries/recovery-id/retry",
            headers={"X-Hermes-Intent": "founder-action"},
            json=payload,
        )

    assert denied.status_code == 403
    assert accepted.status_code == 200
    assert fake.codex_auth_retry == ("recovery-id", payload)


def test_approval_center_binds_displayed_review_digest(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    payload = {
        "reason": "Founder reviewed the exact displayed approval envelope.",
        "expires_in_seconds": 900,
        "expected_review_digest": "a" * 64,
    }
    with TestClient(create_app(settings, control_plane=fake)) as client:
        page = client.get("/").text
        accepted = client.post(
            "/api/approvals/approval-id/approve",
            headers={"X-Hermes-Intent": "founder-action"},
            json=payload,
        )
        missing = client.post(
            "/api/approvals/approval-id/approve",
            headers={"X-Hermes-Intent": "founder-action"},
            json={"reason": payload["reason"], "expires_in_seconds": 900},
        )
    assert accepted.status_code == 200
    assert missing.status_code == 422
    assert fake.approval_decision.expected_review_digest == "a" * 64
    assert 'name="review_digest"' in page
    assert 'name="digest_acknowledged"' in page


def test_approval_resend_requests_a_fresh_notification(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    reason = "Founder requested a fresh approval review link from Mission Control."
    with TestClient(create_app(settings, control_plane=fake)) as client:
        accepted = client.post(
            "/api/tasks/task-id/resend-approval",
            headers={"X-Hermes-Intent": "founder-action"},
            json={"reason": reason},
        )

    assert accepted.status_code == 200
    assert fake.approval_resend == ("task-id", reason)


def test_approval_dialog_surfaces_validation_and_request_failures(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        page = client.get("/").text
        script = client.get("/static/app.js").text

    assert 'id="decision-form" method="dialog" novalidate' in page
    assert 'id="decision-error"' in page
    assert "Enter a decision reason of at least 10 characters." in script
    assert "Confirm that you reviewed the exact digest" in script
    assert (
        'button.textContent = action === "approve" ? "Approving…" : "Rejecting…"'
        in script
    )
    assert (
        'showDecisionError(error.message || "The approval decision could not be recorded.")'
        in script
    )
    assert "Resend to Telegram" in script
    assert "/resend-approval`" in script


def test_approval_dialog_cancel_bypasses_decision_requirements(
    settings: MissionControlSettings,
) -> None:
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        page = client.get("/").text

    decision_dialog = page.split('id="decision-dialog"', maxsplit=1)[1].split(
        "</dialog>", maxsplit=1
    )[0]
    assert (
        '<button type="button" class="secondary" data-close-dialog>Cancel</button>'
        in decision_dialog
    )
    assert (
        'type="button" class="icon-button close" data-close-dialog' in decision_dialog
    )
    assert '<button value="cancel"' not in decision_dialog


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
    assert "/api/knowledge/sources/private/{opaque_id}/content" in paths
    assert "/api/knowledge/sources/canonical/{object_id}/content" in paths


def test_private_source_content_route_separates_ids_and_rejects_paths(
    settings: MissionControlSettings,
) -> None:
    source = Path(settings.knowledge_roots) / "private-note.md"
    source.write_text("# Private note\n\nline two\nline three", encoding="utf-8")
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        client.app.state.knowledge.ingest(str(source))
        catalog = client.get("/api/knowledge/catalog").json()["private"]
        opaque_id = catalog[0]["opaque_id"]
        response = client.get(
            f"/api/knowledge/sources/private/{opaque_id}/content",
            params={"start": 2, "limit": 2},
        )
        path_attempt = client.get(
            f"/api/knowledge/sources/private/{opaque_id}/content",
            params={"path": str(source)},
        )
        canonical_as_private = client.get(
            "/api/knowledge/sources/private/"
            "11111111-1111-4111-8111-111111111111/content"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source_kind"] == "private"
    assert body["range"]["start"] == 2
    assert body["source_digest"]
    assert "path" not in body
    assert path_attempt.status_code == 422
    assert canonical_as_private.status_code == 404


def test_library_catalog_is_server_paginated_and_filterable_without_paths(
    settings: MissionControlSettings,
) -> None:
    root = Path(settings.knowledge_roots)
    for name, title in (
        ("alpha.md", "# Alpha Methods\n\nalpha"),
        ("beta.md", "# Beta Evidence\n\nbeta"),
        ("gamma.md", "# Gamma Notes\n\ngamma"),
    ):
        (root / name).write_text(title, encoding="utf-8")
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        for path in root.iterdir():
            client.app.state.knowledge.ingest(str(path))
        first = client.get(
            "/api/knowledge/catalog",
            params={"kind": "private", "offset": 0, "limit": 2},
        ).json()
        filtered = client.get(
            "/api/knowledge/catalog",
            params={"kind": "private", "q": "gamma", "limit": 10},
        ).json()

    assert first["pagination"] == {
        "offset": 0,
        "limit": 2,
        "total": 3,
        "has_more": True,
    }
    assert [item["title"] for item in first["private"]] == [
        "Alpha Methods",
        "Beta Evidence",
    ]
    assert filtered["pagination"]["total"] == 1
    assert filtered["private"][0]["title"] == "Gamma Notes"
    assert "path" not in filtered["private"][0]


def test_canonical_source_content_route_paginates_lineage_and_pages(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    source_id = "11111111-1111-4111-8111-111111111111"
    with TestClient(create_app(settings, control_plane=fake)) as client:
        lines = client.get(
            f"/api/knowledge/sources/canonical/{source_id}/content",
            params={"start": 2, "limit": 2},
        )
        pages = client.get(
            f"/api/knowledge/sources/canonical/{source_id}/content",
            params={"unit": "page", "start": 2, "limit": 1},
        )
        path_attempt = client.get(
            f"/api/knowledge/sources/canonical/{source_id}/content",
            params={"path": "/srv/private/book.pdf"},
        )
        private_as_canonical = client.get(
            "/api/knowledge/sources/canonical/not-a-uuid/content"
        )

    assert lines.status_code == 200
    body = lines.json()
    assert body["content"] == "Second canonical line.\nThird canonical line."
    assert body["citation"].endswith("#L2-L3")
    assert body["lineage"]["parsers"] == ["pypdf-heldout"]
    assert body["lineage"]["quality"] == "high"
    assert len(body["lineage"]["scientific_object_ids"]) == 2
    assert body["outline"] == [
        {
            "label": "Page 1",
            "level": 1,
            "unit": "page",
            "position": 1,
            "citation": "P1",
        },
        {
            "label": "Page 2",
            "level": 1,
            "unit": "page",
            "position": 2,
            "citation": "P2",
        },
    ]
    assert body["original_assets"][0]["availability"] == "reference_only"
    assert "storage_uri" not in body["original_assets"][0]
    assert pages.status_code == 200
    assert pages.json()["content"] == "Third canonical line."
    assert pages.json()["citation"].endswith("#P2-P2")
    assert path_attempt.status_code == 422
    assert private_as_canonical.status_code == 422


def test_canonical_source_content_version_is_reflected_in_stable_citation(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    fake.evidence_version = "2"
    source_id = "11111111-1111-4111-8111-111111111111"
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get(
            f"/api/knowledge/sources/canonical/{source_id}/content"
        )

    assert response.status_code == 200
    assert response.json()["version"] == "2"
    assert response.json()["citation"].startswith(f"canonical:{source_id}@2#")


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


def test_private_graph_stays_local_and_supports_rooted_path_queries(
    settings: MissionControlSettings,
) -> None:
    fake = FakeControlPlane()
    app = create_app(settings, control_plane=fake)
    source = Path(settings.knowledge_roots) / "private-graph.md"
    source.write_text("# Private graph\n\n[[Liquidity]] and [[Momentum]].", encoding="utf-8")
    app.state.knowledge.ingest(str(source))

    with TestClient(app) as client:
        overview = client.get("/api/knowledge/graph", params={"scope": "private"})
        assert overview.status_code == 200
        document = next(
            node
            for node in overview.json()["nodes"]
            if node["object_type"] == "private_source"
        )
        topic = next(
            node
            for node in overview.json()["nodes"]
            if node["object_type"] == "private_topic"
        )
        response = client.post(
            "/api/knowledge/graph/query",
            json={
                "scope": "private",
                "root_ids": [document["id"]],
                "mode": "paths",
                "target_id": topic["id"],
                "predicates": ["mentions"],
                "direction": "outgoing",
                "max_depth": 2,
                "max_nodes": 20,
                "page_size": 20,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"] == [[document["id"], topic["id"]]]
    assert payload["authorization"] == {
        "boundary": "mission-control-local-only",
        "mixed_scope_allowed": False,
    }
    assert fake.graph_requested is False
    assert not hasattr(fake, "graph_query")


def test_graph_api_rejects_mixed_scope_ids_and_canonical_overview_cursor(
    settings: MissionControlSettings,
) -> None:
    canonical_id = "11111111-1111-4111-8111-111111111111"
    private_id = "private-source:abcdefghijklmnopqrstuvwxyz123456"
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        private_response = client.post(
            "/api/knowledge/graph/query",
            json={"scope": "private", "root_ids": [canonical_id]},
        )
        canonical_response = client.post(
            "/api/knowledge/graph/query",
            json={"scope": "canonical", "root_ids": [private_id]},
        )
        cursor_response = client.get(
            "/api/knowledge/graph",
            params={"scope": "canonical", "cursor": "abcdefgh"},
        )
    assert private_response.status_code == 422
    assert canonical_response.status_code == 422
    assert cursor_response.status_code == 422


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


def test_overview_stream_requires_a_same_origin_loopback_session(settings):
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        response = client.get("/api/overview/events")
        assert response.status_code == 401
        page = client.get("/")
        assert page.status_code == 200
        assert "hermes_overview_session" in client.cookies


def test_workflow_projection_endpoint_is_read_only_and_fails_closed(settings):
    with TestClient(create_app(settings, control_plane=FakeControlPlane())) as client:
        response = client.get("/api/workflows")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "mission-control-workflow-projection-v1"
    assert payload["items"] == []
    assert "not a running native backtest" in payload["claim_boundary"]


def test_agent_detail_endpoint_returns_a_safe_paginated_projection(settings):
    fake = FakeControlPlane()

    async def dashboard(*, refresh: bool = False) -> dict:
        return {
            "agents": [
                {
                    "id": "agent-1",
                    "slug": "reviewer",
                    "display_name": "Reviewer",
                    "role": "reviewer",
                    "machine": "vm1-developer",
                    "hermes_profile": "restricted",
                    "status": "online",
                    "presence": "online",
                    "capabilities": [],
                    "risk_ceiling": 1,
                    "is_enabled": True,
                    "credential": "not-for-browser",
                }
            ]
        }

    async def agent_tasks(agent_id: str, *, offset: int, limit: int) -> list[dict]:
        assert (agent_id, offset, limit) == ("agent-1", 3, 1)
        return []

    fake.dashboard = dashboard
    fake.agent_tasks = agent_tasks
    with TestClient(create_app(settings, control_plane=fake)) as client:
        response = client.get("/api/agents/agent-1/detail?offset=3&limit=1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_history"] == {
        "items": [],
        "offset": 3,
        "limit": 1,
        "has_more": False,
        "source": "canonical_task_assignment",
    }
    assert "credential" not in payload["agent"]
