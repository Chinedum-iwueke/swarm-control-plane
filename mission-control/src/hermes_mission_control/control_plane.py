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
        }

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
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ControlPlaneError("Control plane is currently unreachable.") from exc
        if response.is_success:
            return response.json()
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
