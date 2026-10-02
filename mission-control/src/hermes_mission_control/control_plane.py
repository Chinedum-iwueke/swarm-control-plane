from __future__ import annotations

import asyncio
import copy
import json
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import MissionControlSettings
from .models import ApprovalDecision, IntakeRequest, ProposalDecision


class ControlPlaneError(RuntimeError):
    """A safe, credential-free control-plane error."""


class ControlPlaneClient:
    def __init__(
        self,
        settings: MissionControlSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.normalized_api_url,
            headers={
                "Authorization": f"Bearer {settings.read_token()}",
                "Accept": "application/json",
            },
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )
        self._dashboard_cache: dict[str, Any] | None = None
        self._dashboard_refresh_task: asyncio.Task[dict[str, Any]] | None = None

    async def close(self) -> None:
        if self._dashboard_refresh_task and not self._dashboard_refresh_task.done():
            self._dashboard_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._dashboard_refresh_task
        await self._client.aclose()

    def warm_dashboard(self) -> None:
        """Populate the first dashboard snapshot without delaying app startup."""
        self._ensure_dashboard_refresh()

    async def backtest_activity(self, *, category="all", tier="all", offset=0) -> dict:
        return await self._request(
            "GET",
            "/v1/research/alpha-campaigns/backtests/activity",
            params={"category": category, "tier": tier, "offset": offset, "limit": 50},
        )

    async def dashboard(self) -> dict[str, Any]:
        if self._dashboard_cache is None:
            snapshot = await self._ensure_dashboard_refresh()
            return copy.deepcopy(snapshot)

        snapshot = copy.deepcopy(self._dashboard_cache)
        self._ensure_dashboard_refresh()
        return snapshot

    def _ensure_dashboard_refresh(self) -> asyncio.Task[dict[str, Any]]:
        if (
            self._dashboard_refresh_task is None
            or self._dashboard_refresh_task.done()
        ):
            self._dashboard_refresh_task = asyncio.create_task(
                self._refresh_dashboard_cache()
            )
            self._dashboard_refresh_task.add_done_callback(
                self._consume_background_refresh_error
            )
        return self._dashboard_refresh_task

    @staticmethod
    def _consume_background_refresh_error(
        task: asyncio.Task[dict[str, Any]],
    ) -> None:
        if not task.cancelled():
            task.exception()

    async def _refresh_dashboard_cache(self) -> dict[str, Any]:
        snapshot = await self._load_dashboard()
        self._dashboard_cache = snapshot
        return snapshot

    async def _load_dashboard(self) -> dict[str, Any]:
        fetches = {
            "health": self._request("GET", "/health", authenticated=False),
            "tasks": self._request(
                "GET", "/v1/tasks", params={"limit": 100, "compact": True}
            ),
            "agents": self._request("GET", "/v1/agents"),
            "approvals": self._request(
                "GET", "/v1/approvals", params={"status": "pending"}
            ),
            "approval_center": self._optional_object(
                "/v1/approval-center",
                {
                    "generated_at": None,
                    "counts": {
                        "pending": 0,
                        "actionable": 0,
                        "blocked": 0,
                        "decided": 0,
                    },
                    "items": [],
                },
            ),
            "artifacts": self._request(
                "GET", "/v1/artifacts", params={"limit": 100}
            ),
            "control_scopes": self._request("GET", "/v1/control/scopes"),
            "package_deployments": self._request("GET", "/v1/packages/deployments"),
            "proposals": self._request("GET", "/v1/proposals"),
            "missions": self._request("GET", "/v1/missions"),
            "research_programs": self._request("GET", "/v1/research-programs"),
            "research_cycles": self._request("GET", "/v1/research-programs/cycles"),
            "research_domains": self._optional_collection("/v1/research/domains"),
            "research_intelligence_runs": self._optional_collection(
                "/v1/research/intelligence/runs"
            ),
            "research_domain_readiness": self._optional_collection(
                "/v1/research/curricula/readiness"
            ),
            "research_memory_exports": self._optional_collection(
                "/v1/research/memory-exports"
            ),
            "operational_notes": self._optional_collection("/v1/operational-notes"),
            "research_dataset_manifests": self._optional_collection(
                "/v1/research/data-contracts/manifests"
            ),
            "research_dataset_builds": self._optional_collection(
                "/v1/research/data-contracts/builds"
            ),
            "alpha_campaigns": self._optional_collection(
                "/v1/research/alpha-campaigns"
            ),
            "backtest_activity": self._optional_object(
                "/v1/research/alpha-campaigns/backtests/activity",
                {"items": [], "counts": {}, "total": 0, "unavailable": True},
            ),
            "research_utilization": self._optional_object(
                "/v1/research/utilization/current",
                {
                    "items": [],
                    "claim_boundary": (
                        "No current native capacity snapshot is available."
                    ),
                    "unavailable": True,
                },
            ),
            "alpha_discovery": self._optional_object(
                "/v1/research/alpha-discovery/overview",
                {
                    "mandates": [],
                    "cycles": [],
                    "throughput": {},
                    "stalls": [],
                    "agents": [],
                },
            ),
            "signal_surveillance": self._optional_object(
                "/v1/research/quantitative-receipts/signal-surveillance",
                {
                    "counts": {
                        "families": 0,
                        "trials": 0,
                        "evaluated": 0,
                        "invalid": 0,
                        "question_candidates": 0,
                    },
                    "items": [],
                    "claim_boundary": "No canonical DISC-010 receipt is registered.",
                },
            ),
            "evidence_dossiers": self._optional_collection(
                "/v1/research/memory/dossiers"
            ),
            "evidence_lifecycle_states": self._optional_items(
                "/v1/research/evidence/lifecycle/objects"
            ),
            "blocked_artifact_register": self._optional_object(
                "/v1/research/ingestion/recoveries/blocked-artifacts",
                {"total": 0, "counts_by_classification": {}, "items": []},
            ),
            "fleet_health": self._optional_object(
                "/v1/fleet/health", {"generated_at": None, "machines": []}
            ),
            "observability": self._optional_object(
                "/v1/observability/overview",
                {
                    "generated_at": None,
                    "catalog": None,
                    "summary": {},
                    "services": [],
                    "alerts": [],
                },
            ),
            "execution_telemetry": self._optional_object(
                "/v1/execution/overview",
                {
                    "generated_at": None,
                    "environment": None,
                    "venues": [],
                    "counts": {"current": 0, "stale": 0, "degraded": 0},
                    "claim_boundary": "No canonical venue replay has been published.",
                },
            ),
            "authority": self._optional_object(
                "/v1/authority/overview",
                {"policy": None, "delegations": [], "exceptions": [], "expired": {}},
            ),
            "codex_auth_recoveries": self._optional_collection(
                "/v1/codex-auth/recoveries"
            ),
            "agent_charters": self._optional_collection(
                "/v1/agent-governance/charters"
            ),
            "agent_capability_grants": self._optional_collection(
                "/v1/agent-governance/grants"
            ),
            "workload_identities": self._optional_object(
                "/v1/workload-identities/overview",
                {
                    "enforcement_active": False,
                    "identities": [],
                    "active_secret_policies": 0,
                    "active_emergency_grants": 0,
                    "expiring_credentials": 0,
                },
            ),
            "institutional_lifecycles": self._optional_object(
                "/v1/lifecycles/projections", {"items": [], "count": 0}
            ),
            "lifecycle_consequences": self._optional_object(
                "/v1/lifecycle-consequences", {"items": [], "count": 0}
            ),
            "operations": self._optional_collection("/v1/operations"),
            "surveillance_sources": self._optional_collection(
                "/v1/research/surveillance/sources"
            ),
            "surveillance_candidates": self._optional_collection(
                "/v1/research/surveillance/candidates"
            ),
            "surveillance_digests": self._optional_collection(
                "/v1/research/surveillance/digests"
            ),
            "scientific_review_queue": self._optional_collection(
                "/v1/research/scientific-fidelity/review-queue"
            ),
            "scientific_benchmarks": self._optional_collection(
                "/v1/research/scientific-fidelity/benchmarks"
            ),
            "mathematics_capabilities": self._optional_collection(
                "/v1/research/scientific-fidelity/mathematics/capabilities"
            ),
            "scientific_assurance": self._optional_object(
                "/v1/research/scientific-fidelity/assurance/overview",
                {
                    "counts": {},
                    "requests": [],
                    "receipts": [],
                    "claim_boundary": "Scientific assurance service is unavailable.",
                },
            ),
            "intelligence_evaluation": self._optional_object(
                "/v1/research/intelligence-evaluation/readiness",
                {
                    "status": "not_demonstrated",
                    "domains": {},
                    "limitations": ["evaluation_service_unavailable"],
                },
            ),
            "derived_state": self._optional_object(
                "/v1/research/derived-state/status",
                {
                    "corpus_epoch": None,
                    "pending_changes": 0,
                    "retrieval": {"stale": True},
                    "graph": {"stale": True},
                    "current": False,
                    "latest_run": None,
                    "claim_boundary": "Derived-state service is unavailable.",
                },
            ),
        }
        values = await asyncio.gather(*fetches.values())
        result = dict(zip(fetches, values, strict=True))
        counts: dict[str, int] = {}
        for operation in result["operations"]:
            state = operation.get("state", "unknown")
            counts[state] = counts.get(state, 0) + 1
        result["operation_summary"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": counts,
            "active_total": sum(
                counts.get(state, 0)
                for state in (
                    "queued",
                    "waiting_approval",
                    "running",
                    "blocked",
                    "stalled",
                )
            ),
            "terminal_total": sum(
                counts.get(state, 0)
                for state in ("succeeded", "failed", "cancelled")
            ),
        }
        return result

    async def task_detail(self, task_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/tasks/{task_id}")

    async def adjudicate_scientific_representation(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = {
            "representation_id",
            "reviewer_id",
            "reviewer_role",
            "decision",
            "rationale",
            "gold_payload",
            "corpus_digest",
        }
        if set(payload) - allowed:
            raise ValueError("Unsupported scientific adjudication fields.")
        return await self._request(
            "POST", "/v1/research/scientific-fidelity/adjudications", json=payload
        )

    async def approve_alpha_mandate(
        self, mandate_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if set(payload) != {"expected_mandate_digest", "reason"}:
            raise ValueError("Alpha mandate approval fields are invalid.")
        return await self._request(
            "POST",
            f"/v1/research/alpha-discovery/mandates/{mandate_id}/approve",
            json={**payload, "actor": "founder-operator"},
        )

    async def retry_codex_auth(
        self, recovery_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/v1/codex-auth/recoveries/{recovery_id}/retry", json=payload
        )

    async def scientific_review_context(self, representation_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v1/research/scientific-fidelity/review-context/{representation_id}",
        )

    async def decide_research_cycle(
        self,
        cycle_id: str,
        expected_question_digest: str,
        decision: str,
        rationale: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/research-programs/cycles/{cycle_id}/decision",
            json={
                "expected_question_digest": expected_question_digest,
                "decision": decision,
                "rationale": rationale,
                "decided_by": "founder-operator",
            },
        )

    async def _optional_object(
        self, path: str, fallback: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = await self._client.get(path)
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return fallback
        if response.is_success:
            result = response.json()
            if isinstance(result, dict):
                return result
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def _optional_items(self, path: str) -> list[dict[str, Any]]:
        result = await self._optional_object(path, {"items": []})
        items = result.get("items", [])
        if isinstance(items, list):
            return items
        raise ControlPlaneError("Control plane returned an invalid item collection.")

    async def replay_surveillance_candidate(
        self, publication_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v1/research/surveillance/candidates/{publication_id}/replay",
        )

    async def knowledge_graph(self, *, limit: int = 100) -> dict[str, Any]:
        return await self._request(
            "GET", "/v1/research/graph/overview", params={"limit": limit}
        )

    async def query_knowledge_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/v1/research/graph/query", json=payload)

    async def research_retrieval(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/v1/research/retrieval/query", json=payload)

    async def research_context_pack(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/graph/context-packs", json=payload
        )

    async def mathematics_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/scientific-fidelity/mathematics/search", json=payload
        )

    async def mathematics_context_pack(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/research/scientific-fidelity/mathematics/context-packs",
            json=payload,
        )

    async def replay_research_citation(self, object_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/v1/research/retrieval/objects/{object_id}/replay",
            timeout=120.0,
        )

    async def get_evidence_dossier(self, dossier_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/research/memory/dossiers/{dossier_id}")

    async def replay_evidence_dossier(self, dossier_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/v1/research/memory/dossiers/{dossier_id}/replay"
        )

    async def get_evidence_lifecycle(self, object_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/v1/research/evidence/lifecycle/objects/{object_id}"
        )

    async def transition_evidence_lifecycle(
        self, object_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = {
            "action",
            "authority",
            "reason",
            "successor_object_id",
            "effective_at",
        }
        if set(payload) - allowed:
            raise ValueError("Unsupported evidence lifecycle fields.")
        return await self._request(
            "POST",
            f"/v1/research/evidence/lifecycle/objects/{object_id}/actions",
            json=payload,
        )

    async def transition_operational_note(
        self, note_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = {"action", "reason", "assigned_to", "deferred_until", "evidence"}
        if set(payload) - allowed:
            raise ValueError("Unsupported operational-note fields.")
        return await self._request(
            "POST",
            f"/v1/operational-notes/{note_id}/transitions",
            json={"actor": "founder-mission-control", **payload},
        )

    async def transition_service_alert(
        self, alert_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = {"action", "reason", "silence_seconds"}
        if set(payload) - allowed:
            raise ValueError("Unsupported service-alert fields.")
        return await self._request(
            "POST", f"/v1/observability/alerts/{alert_id}", json=payload
        )

    async def request_operational_note_proposal(
        self, note_id: str, objective: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/operational-notes/{note_id}/proposal-request",
            json={
                "requested_by": "founder-mission-control",
                "objective": objective,
            },
        )

    async def propose_research_memory_sync(self) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/memory-sync/proposals", json={}
        )

    async def create_intake(self, request: IntakeRequest) -> dict[str, Any]:
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        payload = {
            "task_number": f"FOUNDER-{request.kind.upper()}-{now}",
            "project": request.project,
            "task_type": "founder_request",
            "title": request.title,
            "objective": request.objective,
            "priority": 70,
            "risk_level": request.risk_level,
            "created_by": "founder-mission-control",
            "input_contract": {
                "schema_version": 1,
                "request_kind": request.kind,
                "objective": request.objective,
            },
            "expected_outputs": ["reviewed structured execution plan"],
            "acceptance_criteria": request.acceptance_criteria,
            "approval_policy": {
                "kind": "explicit" if request.risk_level >= 2 else "automatic",
                "risk": request.risk_level,
            },
            "approval_required": request.risk_level >= 2,
            "required_capabilities": ["founder-intake"],
            "allowed_machines": ["vm1-developer"],
            "max_attempts": 1,
        }
        return await self._request("POST", "/v1/tasks", json=payload)

    async def conversations(self) -> list[dict[str, Any]]:
        return await self._request(
            "GET", "/v1/conversations", params={"founder_key": "founder:primary"}
        )

    async def conversation_workspace(self, conversation_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", f"/v1/conversations/{conversation_id}/workspace"
        )

    async def create_conversation(self, title: str, message: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/conversations",
            json={
                "founder_key": "founder:primary",
                "channel": "mission-control",
                "title": title,
                "message": message,
            },
        )

    async def add_conversation_turn(
        self, conversation_id: str, message: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/conversations/{conversation_id}/turns",
            json={
                "founder_key": "founder:primary",
                "channel": "mission-control",
                "message": message,
            },
        )

    async def transition_conversation(
        self, conversation_id: str, action: str, reason: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/conversations/{conversation_id}/transitions",
            json={"founder_key": "founder:primary", "action": action, "reason": reason},
        )

    async def decide_proposal(
        self,
        proposal_id: str,
        action: str,
        decision: ProposalDecision,
    ) -> dict[str, Any]:
        if action not in {"materialize", "reject"}:
            raise ValueError("Unsupported proposal action.")
        return await self._request(
            "POST",
            f"/v1/proposals/{proposal_id}/{action}",
            json={
                "actor": "founder-mission-control",
                "reason": decision.reason,
            },
        )

    async def decide_approval(
        self,
        approval_id: str,
        action: str,
        decision: ApprovalDecision,
    ) -> dict[str, Any]:
        if action not in {"approve", "reject"}:
            raise ValueError("Unsupported approval action.")
        return await self._request(
            "POST",
            f"/v1/approval-center/{approval_id}/{action}",
            json={
                "actor": "founder-mission-control",
                "reason": decision.reason,
                "expires_in_seconds": decision.expires_in_seconds,
                "expected_review_digest": decision.expected_review_digest,
            },
        )

    async def resend_approval(self, task_id: str, reason: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/tasks/{task_id}/rearm-approval",
            json={
                "requested_by": "founder-mission-control",
                "reason": reason,
            },
        )

    async def approve_mission(self, mission_id: str, reason: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/missions/{mission_id}/supervision/approve",
            json={"actor": "founder-mission-control", "reason": reason},
        )

    async def set_pause(
        self,
        *,
        paused: bool,
        scope_type: str,
        scope_key: str,
        reason: str,
    ) -> dict[str, Any]:
        if scope_type not in {"global", "machine", "agent"}:
            raise ValueError("Unsupported control scope.")
        return await self._request(
            "POST",
            f"/v1/control/{'pause' if paused else 'resume'}",
            json={
                "scope_type": scope_type,
                "scope_key": scope_key,
                "reason": reason,
                "actor": "founder-mission-control",
            },
        )

    async def register_research_document(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/knowledge/documents", json=payload
        )

    async def create_scientific_ingestion(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/research/ingestion/jobs",
            json=payload,
            timeout=self._settings.ingestion_timeout_seconds,
        )

    async def scientific_ingestion_by_digest(
        self, content_digest: str
    ) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"/v1/research/ingestion/jobs/by-digest/{content_digest}",
                timeout=self._settings.ingestion_timeout_seconds,
            )
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return None
        if response.is_success:
            return response.json()
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def scientific_ingestion_by_id(self, job_id: str) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"/v1/research/ingestion/jobs/{job_id}",
                timeout=self._settings.request_timeout_seconds,
            )
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return None
        if response.is_success:
            return response.json()
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def process_scientific_ingestion(self, job_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/research/ingestion/jobs/{job_id}/process",
            timeout=self._settings.ingestion_timeout_seconds,
        )

    async def recovered_scientific_ingestion(
        self, original_job_id: str
    ) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"/v1/research/ingestion/recoveries/by-original-job/{original_job_id}",
                timeout=self._settings.request_timeout_seconds,
            )
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return None
        if response.is_success:
            return response.json()
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def reconcile_corpus(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/corpus-sync/runs", json=payload
        )

    async def rebuild_corpus_projections(self, project: str) -> dict[str, Any]:
        run = await self._request(
            "POST",
            "/v1/research/derived-state/reconciliations",
            json={"requested_by": "founder-mission-control", "force_full": False},
            timeout=self._settings.projection_rebuild_timeout_seconds,
        )
        return {
            "evidence": {
                "project": project,
                "scheduled": run is not None,
                "reconciliation_id": run.get("id") if run else None,
                "state": run.get("state") if run else "current",
                "source_epoch": run.get("source_epoch_target") if run else None,
                "strategy": run.get("strategy") if run else "no_change",
            }
        }

    async def register_research_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/research/knowledge/document-bundles", json=payload
        )

    async def research_document_by_digest(
        self, content_digest: str
    ) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"/v1/research/knowledge/documents/by-digest/{content_digest}"
            )
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return None
        if response.is_success:
            return response.json()
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def register_research_chunk(
        self, document_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v1/research/knowledge/documents/{document_id}/chunks",
            json=payload,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Any:
        headers = kwargs.pop("headers", {})
        if not authenticated:
            headers["Authorization"] = ""
        try:
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.is_success:
            return response.json()
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )

    async def _optional_collection(self, path: str) -> list[dict[str, Any]]:
        try:
            response = await self._client.get(path)
        except httpx.TransportError as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.status_code == 404:
            return []
        if response.is_success:
            value = response.json()
            if isinstance(value, list):
                return value
        detail = _safe_detail(response)
        raise ControlPlaneError(
            f"Control plane returned HTTP {response.status_code}: {detail}"
        )


def _safe_detail(response: httpx.Response) -> str:
    try:
        value = response.json()
        detail = (
            value.get("detail", "Request failed.") if isinstance(value, dict) else value
        )
        rendered = json.dumps(detail, ensure_ascii=True)
    except (ValueError, TypeError):
        rendered = "Request failed."
    return rendered[:1000]
