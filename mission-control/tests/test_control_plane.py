from __future__ import annotations

import json

import httpx
import pytest

from hermes_mission_control.config import MissionControlSettings
from hermes_mission_control.control_plane import (
    ControlPlaneClient,
    ControlPlaneError,
)
from hermes_mission_control.models import (
    ApprovalDecision,
    IntakeRequest,
    ProposalDecision,
)


@pytest.mark.asyncio
async def test_dashboard_uses_bearer_without_exposing_token(
    settings: MissionControlSettings,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path.endswith("/blocked-artifacts"):
            return httpx.Response(
                200,
                json={"total": 0, "counts_by_classification": {}, "items": []},
            )
        if request.url.path.endswith("/evidence/lifecycle/objects"):
            return httpx.Response(200, json={"items": [], "count": 0})
        if request.url.path == "/v1/fleet/health":
            return httpx.Response(200, json={"generated_at": None, "machines": []})
        if request.url.path == "/v1/observability/overview":
            return httpx.Response(
                200,
                json={
                    "generated_at": None,
                    "catalog": None,
                    "summary": {},
                    "services": [],
                    "alerts": [],
                },
            )
        if request.url.path == "/v1/operations/summary":
            return httpx.Response(
                200,
                json={
                    "generated_at": None,
                    "counts": {},
                    "active_total": 0,
                    "terminal_total": 0,
                },
            )
        if request.url.path == "/v1/authority/overview":
            return httpx.Response(
                200,
                json={
                    "policy": {"version": "1.0.0", "status": "active"},
                    "delegations": [],
                    "exceptions": [],
                    "expired": {},
                },
            )
        if request.url.path == "/v1/workload-identities/overview":
            return httpx.Response(
                200,
                json={
                    "enforcement_active": True,
                    "identities": [],
                    "active_secret_policies": 0,
                    "active_emergency_grants": 0,
                    "expiring_credentials": 0,
                },
            )
        if request.url.path == "/v1/lifecycles/projections":
            return httpx.Response(200, json={"items": [], "count": 0})
        if request.url.path == "/v1/lifecycle-consequences":
            return httpx.Response(200, json={"items": [], "count": 0})
        if request.url.path == "/v1/approval-center":
            return httpx.Response(
                200,
                json={
                    "generated_at": None,
                    "counts": {
                        "pending": 0,
                        "actionable": 0,
                        "blocked": 0,
                        "decided": 0,
                    },
                    "items": [],
                },
            )
        if request.url.path == "/v1/research/intelligence-evaluation/readiness":
            return httpx.Response(
                200,
                json={
                    "status": "not_demonstrated",
                    "domains": {},
                    "limitations": ["no_evaluation_suite"],
                },
            )
        return httpx.Response(200, json=[])

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        result = await client.dashboard()
    finally:
        await client.close()
    assert result["health"]["status"] == "ok"
    authenticated = [request for request in seen if request.url.path != "/health"]
    assert authenticated
    assert all(
        request.headers["authorization"] == "Bearer operator-token-that-is-long-enough"
        for request in authenticated
    )
    assert "operator-token-that-is-long-enough" not in json.dumps(result)
    assert "evidence_dossiers" in result
    assert "evidence_lifecycle_states" in result
    assert "surveillance_candidates" in result
    assert result["blocked_artifact_register"]["total"] == 0
    assert result["fleet_health"]["machines"] == []
    assert result["observability"]["services"] == []
    assert result["operations"] == []
    assert result["operation_summary"]["active_total"] == 0
    assert result["authority"]["policy"]["status"] == "active"
    assert result["workload_identities"]["enforcement_active"] is True
    assert result["institutional_lifecycles"]["count"] == 0
    assert result["lifecycle_consequences"]["count"] == 0
    assert result["intelligence_evaluation"]["status"] == "not_demonstrated"


@pytest.mark.asyncio
async def test_surveillance_replay_uses_authenticated_read_only_route(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["authorization"] == (
            "Bearer operator-token-that-is-long-enough"
        )
        return httpx.Response(200, json={"exact_replay": True})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        replay = await client.replay_surveillance_candidate("publication-id")
    finally:
        await client.close()
    assert replay["exact_replay"] is True
    assert seen == [
        (
            "GET",
            "/v1/research/surveillance/candidates/publication-id/replay",
        )
    ]


@pytest.mark.asyncio
async def test_service_alert_action_uses_bounded_authenticated_route(
    settings: MissionControlSettings,
) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"state": "acknowledged"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        result = await client.transition_service_alert(
            "alert-id", {"action": "acknowledge", "reason": "Founder owns response."}
        )
    finally:
        await client.close()
    assert result["state"] == "acknowledged"
    assert seen == [
        (
            "POST",
            "/v1/observability/alerts/alert-id",
            {"action": "acknowledge", "reason": "Founder owns response."},
        )
    ]


@pytest.mark.asyncio
async def test_research_copilot_uses_only_canonical_read_routes(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/replay"):
            assert request.extensions["timeout"]["read"] == 120.0
        seen.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        assert request.headers["authorization"] == (
            "Bearer operator-token-that-is-long-enough"
        )
        return httpx.Response(200, json={"ok": True})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.research_retrieval({"query": "momentum"})
        await client.research_context_pack(
            {"query": "momentum", "object_ids": ["object-id"]}
        )
        await client.replay_research_citation("object-id")
    finally:
        await client.close()
    assert seen == [
        ("POST", "/v1/research/retrieval/query", {"query": "momentum"}),
        (
            "POST",
            "/v1/research/graph/context-packs",
            {"query": "momentum", "object_ids": ["object-id"]},
        ),
        ("GET", "/v1/research/retrieval/objects/object-id/replay", None),
    ]


@pytest.mark.asyncio
async def test_graph_explorer_uses_authenticated_read_only_query(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        return httpx.Response(200, json={"nodes": [], "edges": []})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    payload = {
        "root_ids": ["11111111-1111-4111-8111-111111111111"],
        "max_nodes": 80,
    }
    try:
        await client.query_knowledge_graph(payload)
    finally:
        await client.close()
    assert seen == [("POST", "/v1/research/graph/query", payload)]


@pytest.mark.asyncio
async def test_conversation_client_uses_canonical_cross_channel_identity(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.method,
                request.url.path,
                json.loads(request.content) if request.content else None,
            )
        )
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"conversation": {}})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.conversations()
        await client.conversation_workspace("conversation-id")
        await client.create_conversation("BTC research", "Test the risk-off claim.")
        await client.add_conversation_turn("conversation-id", "Use January 2022.")
        await client.transition_conversation(
            "conversation-id", "finish", "Founder completed the thread."
        )
    finally:
        await client.close()

    assert seen[0] == ("GET", "/v1/conversations", None)
    assert seen[1] == (
        "GET",
        "/v1/conversations/conversation-id/workspace",
        None,
    )
    assert seen[2][2]["founder_key"] == "founder:primary"
    assert seen[2][2]["channel"] == "mission-control"
    assert seen[3][2]["message"] == "Use January 2022."
    assert seen[4][2]["action"] == "finish"


@pytest.mark.asyncio
async def test_dossier_client_uses_authenticated_read_only_routes(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        assert request.headers["authorization"] == (
            "Bearer operator-token-that-is-long-enough"
        )
        if request.url.path.endswith("/replay"):
            return httpx.Response(200, json={"exact_replay": True, "impacts": []})
        return httpx.Response(200, json={"id": "dossier-id"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        dossier = await client.get_evidence_dossier("dossier-id")
        replay = await client.replay_evidence_dossier("dossier-id")
    finally:
        await client.close()
    assert dossier["id"] == "dossier-id"
    assert replay["exact_replay"] is True
    assert seen == [
        ("GET", "/v1/research/memory/dossiers/dossier-id"),
        ("GET", "/v1/research/memory/dossiers/dossier-id/replay"),
    ]


@pytest.mark.asyncio
async def test_lifecycle_client_reads_and_submits_only_structured_actions(
    settings: MissionControlSettings,
) -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"dossier_digest": "a" * 64})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    payload = {
        "action": "retract",
        "authority": "knowledge-steward",
        "reason": "Evidence was retracted by its source.",
        "successor_object_id": None,
        "effective_at": "2026-08-21T00:00:00Z",
    }
    try:
        await client.get_evidence_lifecycle("object-id")
        await client.transition_evidence_lifecycle("object-id", payload)
        with pytest.raises(ValueError, match="Unsupported"):
            await client.transition_evidence_lifecycle(
                "object-id", {**payload, "command": "rm -rf /"}
            )
    finally:
        await client.close()
    assert seen == [
        ("GET", "/v1/research/evidence/lifecycle/objects/object-id", None),
        ("POST", "/v1/research/evidence/lifecycle/objects/object-id/actions", payload),
    ]


@pytest.mark.asyncio
async def test_intake_is_structured_and_non_executable(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(201, json={"id": "task-id"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.create_intake(
            IntakeRequest(
                kind="mission",
                project="swarm-control-plane",
                title="Build the next bounded milestone",
                objective="Prepare a reviewed implementation plan and evidence.",
                risk_level=1,
                acceptance_criteria=["Plan is reviewable."],
            )
        )
    finally:
        await client.close()
    assert captured["task_type"] == "founder_request"
    assert captured["required_capabilities"] == ["founder-intake"]
    assert captured["allowed_machines"] == ["vm1-developer"]
    assert set(captured["input_contract"]) == {
        "schema_version",
        "request_kind",
        "objective",
    }
    assert "command" not in json.dumps(captured).lower()


@pytest.mark.asyncio
async def test_high_risk_intake_requires_approval(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(201, json={"id": "task-id"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.create_intake(
            IntakeRequest(
                kind="task",
                project="operations",
                title="Review a production proposal",
                objective="Review the proposal without executing any operation.",
                risk_level=3,
            )
        )
    finally:
        await client.close()
    assert captured["approval_required"] is True
    assert captured["approval_policy"] == {"kind": "explicit", "risk": 3}


@pytest.mark.asyncio
async def test_approval_body_is_explicit(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"status": "approved"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.decide_approval(
            "approval-id",
            "approve",
            ApprovalDecision(
                reason="Founder reviewed the exact bounded plan.",
                expires_in_seconds=600,
                expected_review_digest="a" * 64,
            ),
        )
    finally:
        await client.close()
    assert captured == {
        "actor": "founder-mission-control",
        "reason": "Founder reviewed the exact bounded plan.",
        "expires_in_seconds": 600,
        "expected_review_digest": "a" * 64,
    }


@pytest.mark.asyncio
async def test_api_error_is_bounded_and_token_free(
    settings: MissionControlSettings,
) -> None:
    token = settings.read_token()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "database unavailable"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ControlPlaneError) as raised:
            await client.dashboard()
    finally:
        await client.close()
    assert "HTTP 500" in str(raised.value)
    assert token not in str(raised.value)


@pytest.mark.asyncio
async def test_proposal_materialization_is_an_explicit_founder_action(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json={"id": "task-id"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.decide_proposal(
            "proposal-id",
            "materialize",
            ProposalDecision(reason="Founder reviewed the complete bounded proposal."),
        )
    finally:
        await client.close()
    assert captured == {
        "path": "/v1/proposals/proposal-id/materialize",
        "body": {
            "actor": "founder-mission-control",
            "reason": "Founder reviewed the complete bounded proposal.",
        },
    }


@pytest.mark.asyncio
async def test_note_remediation_enters_founder_intake_planning(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"task_type": "founder_request"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        result = await client.request_operational_note_proposal(
            "note-id", "Measure storage growth before proposing remediation."
        )
    finally:
        await client.close()
    assert result["task_type"] == "founder_request"
    assert captured == {
        "path": "/v1/operational-notes/note-id/proposal-request",
        "body": {
            "requested_by": "founder-mission-control",
            "objective": "Measure storage growth before proposing remediation.",
        },
    }


@pytest.mark.asyncio
async def test_projection_rebuild_uses_maintenance_timeout(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(201, json={"status": "succeeded"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.rebuild_corpus_projections("systematic-research")
    finally:
        await client.close()

    assert captured["path"] == "/v1/research/corpus/projections/recover"
    assert captured["timeout"]["read"] == 600.0


@pytest.mark.asyncio
async def test_daily_research_decision_is_digest_bound(
    settings: MissionControlSettings,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "cycle-id"})

    client = ControlPlaneClient(settings, transport=httpx.MockTransport(handler))
    try:
        await client.decide_research_cycle(
            "cycle-id",
            "a" * 64,
            "approved",
            "Founder approved the evidence-grounded question.",
        )
    finally:
        await client.close()

    assert captured == {
        "path": "/v1/research-programs/cycles/cycle-id/decision",
        "body": {
            "expected_question_digest": "a" * 64,
            "decision": "approved",
            "rationale": "Founder approved the evidence-grounded question.",
            "decided_by": "founder-operator",
        },
    }
