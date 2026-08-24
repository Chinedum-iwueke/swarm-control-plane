from __future__ import annotations

import json
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

    async def close(self) -> None:
        await self._client.aclose()

    async def dashboard(self) -> dict[str, Any]:
        health = await self._request("GET", "/health", authenticated=False)
        tasks = await self._request("GET", "/v1/tasks", params={"limit": 100})
        agents = await self._request("GET", "/v1/agents")
        approvals = await self._request("GET", "/v1/approvals")
        artifacts = await self._request("GET", "/v1/artifacts", params={"limit": 100})
        scopes = await self._request("GET", "/v1/control/scopes")
        deployments = await self._request("GET", "/v1/packages/deployments")
        proposals = await self._request("GET", "/v1/proposals")
        missions = await self._request("GET", "/v1/missions")
        research_programs = await self._request("GET", "/v1/research-programs")
        research_cycles = await self._request("GET", "/v1/research-programs/cycles")
        research_domains = await self._optional_collection("/v1/research/domains")
        intelligence_runs = await self._optional_collection(
            "/v1/research/intelligence/runs"
        )
        domain_readiness = await self._optional_collection(
            "/v1/research/curricula/readiness"
        )
        memory_exports = await self._optional_collection("/v1/research/memory-exports")
        operational_notes = await self._optional_collection("/v1/operational-notes")
        dataset_manifests = await self._optional_collection(
            "/v1/research/data-contracts/manifests"
        )
        dataset_builds = await self._optional_collection(
            "/v1/research/data-contracts/builds"
        )
        evidence_dossiers = await self._optional_collection(
            "/v1/research/memory/dossiers"
        )
        lifecycle_states = await self._optional_items(
            "/v1/research/evidence/lifecycle/objects"
        )
        blocked_artifacts = await self._optional_object(
            "/v1/research/ingestion/recoveries/blocked-artifacts",
            {"total": 0, "counts_by_classification": {}, "items": []},
        )
        fleet_health = await self._optional_object(
            "/v1/fleet/health", {"generated_at": None, "machines": []}
        )
        operations = await self._optional_collection("/v1/operations")
        operation_summary = await self._optional_object(
            "/v1/operations/summary",
            {"generated_at": None, "counts": {}, "active_total": 0, "terminal_total": 0},
        )
        surveillance_sources = await self._optional_collection(
            "/v1/research/surveillance/sources"
        )
        surveillance_candidates = await self._optional_collection(
            "/v1/research/surveillance/candidates"
        )
        surveillance_digests = await self._optional_collection(
            "/v1/research/surveillance/digests"
        )
        return {
            "health": health,
            "tasks": tasks,
            "agents": agents,
            "approvals": approvals,
            "artifacts": artifacts,
            "control_scopes": scopes,
            "package_deployments": deployments,
            "proposals": proposals,
            "missions": missions,
            "research_programs": research_programs,
            "research_cycles": research_cycles,
            "research_domains": research_domains,
            "research_intelligence_runs": intelligence_runs,
            "research_domain_readiness": domain_readiness,
            "research_memory_exports": memory_exports,
            "operational_notes": operational_notes,
            "research_dataset_manifests": dataset_manifests,
            "research_dataset_builds": dataset_builds,
            "evidence_dossiers": evidence_dossiers,
            "evidence_lifecycle_states": lifecycle_states,
            "blocked_artifact_register": blocked_artifacts,
            "fleet_health": fleet_health,
            "operations": operations,
            "operation_summary": operation_summary,
            "surveillance_sources": surveillance_sources,
            "surveillance_candidates": surveillance_candidates,
            "surveillance_digests": surveillance_digests,
        }

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
            f"/v1/approvals/{approval_id}/{action}",
            json={
                "actor": "founder-mission-control",
                "reason": decision.reason,
                "expires_in_seconds": decision.expires_in_seconds,
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
        return await self._request(
            "POST",
            "/v1/research/corpus/projections/recover",
            json={"project": project, "requested_by": "founder-mission-control"},
            timeout=self._settings.projection_rebuild_timeout_seconds,
        )

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
