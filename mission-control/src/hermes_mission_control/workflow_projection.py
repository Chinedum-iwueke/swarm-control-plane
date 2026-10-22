"""Truthful workflow-instance projections from bounded control-plane records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_ACTIVE = frozenset({"queued", "waiting_approval", "running", "blocked", "stalled"})
_TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


def project_workflows(
    snapshot: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Project only facts present in a dashboard snapshot.

    A campaign can be active while it awaits engineering or a reviewer. It is
    never called a running native backtest unless the receipt-truthful backtest
    projection has a matching live execute-stage leaf task.
    """

    observed_at = now or datetime.now(timezone.utc)
    operations = [
        item for item in snapshot.get("operations", []) if isinstance(item, dict)
    ]
    campaigns = [
        item for item in snapshot.get("alpha_campaigns", []) if isinstance(item, dict)
    ]
    activity = snapshot.get("backtest_activity", {})
    backtests = activity.get("items", []) if isinstance(activity, dict) else []
    live_by_campaign = {
        str(item.get("campaign_id")): item
        for item in backtests
        if isinstance(item, dict)
        and item.get("campaign_id")
        and item.get("stage") == "execute"
        and item.get("status") in {"running", "leased"}
    }

    items = [_operation_instance(operation, observed_at) for operation in operations]
    items.extend(
        _campaign_instance(campaign, live_by_campaign.get(str(campaign.get("id"))))
        for campaign in campaigns
        if campaign.get("id")
    )
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    items.sort(key=lambda item: _sort_bucket(item["state"]))
    return {
        "schema_version": "mission-control-workflow-projection-v1",
        "generated_at": observed_at.isoformat(),
        "items": items,
        "count": len(items),
        "claim_boundary": (
            "Workflow instances are derived from canonical operations, campaigns, and "
            "receipt-truthful execute-stage tasks. A campaign is not a running native "
            "backtest without a live leaf-run signal."
        ),
    }


def _operation_instance(operation: dict[str, Any], now: datetime) -> dict[str, Any]:
    detail = (
        operation.get("detail") if isinstance(operation.get("detail"), dict) else {}
    )
    links = operation.get("links") if isinstance(operation.get("links"), dict) else {}
    state = str(operation.get("state") or "unknown")
    heartbeat_at = operation.get("heartbeat_at")
    stale = state == "stalled" or _heartbeat_stale(heartbeat_at, detail, now)
    if stale and state not in _TERMINAL:
        state = "stalled"
    source_event_ids = (
        detail.get("source_event_ids") or links.get("source_event_ids") or []
    )
    if not isinstance(source_event_ids, list):
        source_event_ids = []
    terminal_receipt = detail.get("terminal_receipt") or links.get("terminal_receipt")
    blockers = (
        detail.get("blockers") if isinstance(detail.get("blockers"), list) else []
    )
    if state in {"blocked", "stalled"} and operation.get("error_summary"):
        blockers = [*blockers, str(operation["error_summary"])]
    workflow_name = str(detail.get("workflow") or operation.get("kind") or "unknown")
    return {
        "instance_id": f"operation:{operation.get('id') or operation.get('operation_key')}",
        "instance_kind": "operation",
        "workflow": {"name": workflow_name, "version": detail.get("workflow_version")},
        "state": state,
        "stale": stale,
        "title": operation.get("title") or workflow_name,
        "project": operation.get("project"),
        "owner": {"type": operation.get("owner_type"), "id": operation.get("owner_id")},
        "machine": operation.get("machine"),
        "stages": [_stage(operation.get("phase"), state)],
        "current_leaf": {
            "kind": "operation",
            "id": str(operation.get("id") or operation.get("operation_key")),
            "state": state,
            "phase": operation.get("phase"),
            "heartbeat_at": heartbeat_at,
        },
        "entry_evidence": _compact_evidence(
            operation.get("input_digest"), source_event_ids
        ),
        "exit_evidence": _compact_evidence(
            terminal_receipt or operation.get("record_digest"), source_event_ids
        ),
        "source_event_ids": source_event_ids,
        "blockers": blockers,
        "retries": {
            "retryable": bool(operation.get("retryable")),
            "attempt": detail.get("attempt"),
            "max_attempts": detail.get("max_attempts"),
        },
        "terminal_outcome": state if state in _TERMINAL else None,
        "updated_at": operation.get("updated_at") or heartbeat_at or "",
    }


def _campaign_instance(
    campaign: dict[str, Any], live_leaf: dict[str, Any] | None
) -> dict[str, Any]:
    campaign_state = str(campaign.get("status") or "unknown")
    phase = campaign.get("phase") or "unknown"
    live = live_leaf is not None
    leaf = (
        {
            "kind": "native_backtest",
            "id": live_leaf.get("task_id"),
            "state": live_leaf.get("status"),
            "phase": live_leaf.get("progress", {}).get("phase") or "execute",
            "heartbeat_at": live_leaf.get("heartbeat_at"),
        }
        if live
        else None
    )
    return {
        "instance_id": f"alpha-campaign:{campaign['id']}",
        "instance_kind": "alpha_campaign",
        "workflow": {"name": "alpha-campaign", "version": campaign.get("version")},
        "state": campaign_state,
        "stale": False,
        "title": campaign.get("campaign_key") or "Alpha campaign",
        "project": campaign.get("project"),
        "owner": {"type": "campaign", "id": str(campaign["id"])},
        "machine": leaf.get("machine") if leaf else None,
        "stages": [
            _stage(phase, campaign_state),
            _stage("native_bulletproof", "running" if live else "not_running"),
        ],
        "current_leaf": leaf,
        "native_backtest": {
            "state": "running" if live else "not_running",
            "basis": "live_execute_stage_leaf" if live else "no_live_leaf_run",
        },
        "entry_evidence": _compact_evidence(campaign.get("campaign_digest"), []),
        "exit_evidence": _compact_evidence(None, []),
        "source_event_ids": [],
        "blockers": _campaign_blockers(campaign),
        "retries": {"retryable": False, "attempt": None, "max_attempts": None},
        "terminal_outcome": campaign_state if campaign_state in _TERMINAL else None,
        "updated_at": campaign.get("updated_at") or campaign.get("created_at") or "",
    }


def _campaign_blockers(campaign: dict[str, Any]) -> list[str]:
    reason = campaign.get("terminal_reason")
    if isinstance(reason, dict):
        category = reason.get("category")
        return [str(category)] if category else []
    return [str(reason)] if reason else []


def _heartbeat_stale(value: Any, detail: dict[str, Any], now: datetime) -> bool:
    if not isinstance(value, str):
        return False
    try:
        heartbeat = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if heartbeat.tzinfo is None:
        return True
    threshold = detail.get("heartbeat_slo_seconds", 180)
    try:
        return (now - heartbeat).total_seconds() > float(threshold)
    except (TypeError, ValueError):
        return True


def _compact_evidence(digest: Any, event_ids: list[Any]) -> dict[str, Any]:
    return {
        "digest": digest if isinstance(digest, str) else None,
        "source_event_ids": event_ids,
    }


def _stage(name: Any, state: str) -> dict[str, str]:
    return {"name": str(name or "unknown"), "state": state}


def _sort_bucket(state: str) -> int:
    if state == "running":
        return 0
    if state in _ACTIVE:
        return 1
    if state in _TERMINAL:
        return 2
    return 3
