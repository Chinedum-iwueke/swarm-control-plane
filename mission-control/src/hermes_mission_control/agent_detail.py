"""Safe, source-bound agent detail projections for Mission Control."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .freshness import build_snapshot_provenance
from .workflow_projection import project_workflows

_ACTIVE = frozenset({"queued", "leased", "running", "pending_approval"})


def project_agent_detail(
    snapshot: dict[str, Any],
    agent_id: str,
    task_history: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    agent = next(
        (
            item
            for item in snapshot.get("agents", [])
            if str(item.get("id")) == str(agent_id)
        ),
        None,
    )
    if agent is None:
        return None
    observed_at = now or datetime.now(timezone.utc)
    deployment = _active_deployment(snapshot, agent_id)
    charter = _active_for_agent(snapshot.get("agent_charters", []), agent_id)
    grants = _all_active(snapshot.get("agent_capability_grants", []), agent_id)
    identity = _active_for_agent(
        (snapshot.get("workload_identities") or {}).get("identities", []), agent_id
    )
    operations = _owned_operations(snapshot.get("operations", []), agent_id)
    current_lease = next(
        (item for item in operations if item.get("state") in _ACTIVE),
        None,
    ) or next((item for item in task_history if item.get("status") in _ACTIVE), None)
    workflow_items = project_workflows(snapshot, now=observed_at).get("items", [])
    memberships = [
        _workflow_membership(item)
        for item in workflow_items
        if str((item.get("owner") or {}).get("id")) == str(agent_id)
    ]
    task_ids = {str(item.get("id")) for item in task_history}
    artifacts = [
        _artifact_reference(item)
        for item in snapshot.get("artifacts", [])
        if str(item.get("task_id")) in task_ids
    ]
    provenance = build_snapshot_provenance(
        {
            # Presence freshness is anchored only to the heartbeat. A metadata
            # update must never make a stale worker appear live.
            "agents": [{"last_heartbeat_at": agent.get("last_heartbeat_at")}],
            "tasks": task_history,
        },
        now=observed_at,
    )
    return {
        "schema_version": "mission-control-agent-detail-v1",
        "generated_at": observed_at.isoformat(),
        "agent": _safe_agent(agent),
        "deployment": _deployment_summary(deployment),
        "charter": _charter_summary(charter),
        "grants": [_grant_summary(item) for item in grants],
        "workload_identity": _identity_summary(identity),
        "current_lease": _lease_summary(current_lease),
        "task_history": {
            "items": [_task_summary(item) for item in task_history],
            "offset": offset,
            "limit": limit,
            "has_more": len(task_history) == limit,
            "source": "canonical_task_assignment",
        },
        "heartbeat_history": {
            "items": _heartbeat_observations(agent),
            "availability": "current_observation_only",
            "claim_boundary": "The canonical agent projection currently exposes the latest heartbeat, not a retained heartbeat series.",
        },
        "workflow_memberships": memberships,
        "reporting_relationship": _reporting_relationship(agent),
        "references": {"artifacts": artifacts, "logs": _log_references(operations)},
        "provenance": {
            "presence": provenance.sources["agents"].model_dump(mode="json"),
            "task_status": provenance.sources["tasks"].model_dump(mode="json"),
        },
        "claim_boundary": (
            "No credential, lease token, package signature, or secret reference is included. "
            "Reporting relationships remain unknown unless explicitly recorded by the source."
        ),
    }


def _active_deployment(
    snapshot: dict[str, Any], agent_id: str
) -> dict[str, Any] | None:
    candidates = [
        item
        for item in snapshot.get("package_deployments", [])
        if str((item.get("deployment") or {}).get("agent_id")) == str(agent_id)
        and (item.get("deployment") or {}).get("is_active")
    ]
    return candidates[-1] if candidates else None


def _active_for_agent(items: Any, agent_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get("agent_id")) == str(agent_id)
            and item.get("status") == "active"
        ),
        None,
    )


def _all_active(items: Any, agent_id: str) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if isinstance(item, dict)
        and str(item.get("agent_id")) == str(agent_id)
        and item.get("status") == "active"
    ]


def _owned_operations(items: Any, agent_id: str) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("owner_id")) == str(agent_id)
    ]


def _safe_agent(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        key: agent.get(key)
        for key in (
            "id",
            "slug",
            "display_name",
            "role",
            "machine",
            "hermes_profile",
            "runtime",
            "runtime_version",
            "status",
            "presence",
            "capabilities",
            "risk_ceiling",
            "is_enabled",
            "last_heartbeat_at",
            "created_at",
            "updated_at",
        )
    }


def _deployment_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    package = item.get("package") or {}
    deployment = item.get("deployment") or {}
    return {
        "id": deployment.get("id"),
        "is_active": deployment.get("is_active"),
        "deployed_at": deployment.get("deployed_at"),
        "package_id": package.get("id"),
        "package_name": package.get("name"),
        "package_version": package.get("version"),
        "manifest_digest": package.get("manifest_digest"),
        "source_commit": package.get("source_commit"),
    }


def _charter_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    manifest = item.get("manifest") or {}
    return {
        "id": item.get("id"),
        "version": item.get("version"),
        "manifest_digest": item.get("manifest_digest"),
        "role": manifest.get("role"),
        "responsibilities": manifest.get("responsibilities", []),
        "capabilities": manifest.get("capabilities", []),
        "allowed_task_types": manifest.get("allowed_task_types", []),
        "risk_ceiling": manifest.get("risk_ceiling"),
    }


def _grant_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "id",
            "capability",
            "machine",
            "task_types",
            "repositories",
            "risk_ceiling",
            "accountable_owner",
            "expires_at",
            "record_digest",
        )
    }


def _identity_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        key: item.get(key)
        for key in (
            "id",
            "version",
            "machine",
            "audience",
            "scopes",
            "accountable_owner",
            "manifest_digest",
            "valid_from",
            "expires_at",
        )
    }


def _lease_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        key: item.get(key)
        for key in (
            "id",
            "task_number",
            "title",
            "status",
            "phase",
            "machine",
            "heartbeat_at",
            "updated_at",
            "operation_key",
        )
    }


def _task_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "id",
            "task_number",
            "title",
            "project",
            "task_type",
            "status",
            "risk_level",
            "attempt_count",
            "max_attempts",
            "updated_at",
            "completed_at",
        )
    }


def _heartbeat_observations(agent: dict[str, Any]) -> list[dict[str, Any]]:
    value = agent.get("last_heartbeat_at")
    return (
        [
            {
                "observed_at": value,
                "status": agent.get("status"),
                "presence": agent.get("presence"),
            }
        ]
        if value
        else []
    )


def _workflow_membership(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("instance_id", "title", "state", "machine", "current_leaf")
    }


def _reporting_relationship(agent: dict[str, Any]) -> dict[str, Any]:
    value = agent.get("reporting_relationship")
    if isinstance(value, dict):
        return {"status": "recorded", **value}
    return {"status": "unknown", "reason": "no_authoritative_relationship_record"}


def _artifact_reference(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "id",
            "task_id",
            "name",
            "artifact_type",
            "sha256",
            "verification_status",
            "location",
        )
    }


def _log_references(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    references = []
    for operation in operations:
        links = operation.get("links") or {}
        if isinstance(links, dict) and links.get("log"):
            references.append(
                {"operation_id": operation.get("id"), "reference": links["log"]}
            )
    return references
