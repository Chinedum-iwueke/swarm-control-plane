"""Evidence-bound investor walkthrough projection and local rehearsal journal."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

_ACTIVE_WORKFLOW_STATES = {"running", "queued", "waiting_approval", "blocked", "stalled"}
_TERMINAL_BACKTEST_STATES = {"succeeded", "failed", "cancelled"}
_DECISION_EVENTS = {"signal_decision", "candidate_decision", "risk_decision"}
_FILL_EVENTS = {"fill", "partial_fill", "full_fill"}
_RECONCILIATION_EVENTS = {"reconciliation", "position_reconciliation"}


def project_investor_walkthrough(
    snapshot: dict[str, Any],
    workflows: dict[str, Any],
    venue_history: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Select one bounded canonical chain, disclosing every missing link."""

    observed_at = now or datetime.now(timezone.utc)
    workflow = _select_workflow(workflows.get("items", []))
    agent = _select_responsible_agent(snapshot, workflow)
    backtest = _select_terminal_backtest(snapshot.get("backtest_activity", {}))
    demo_event = _select_demo_event(venue_history.get("events", []))
    provenance = snapshot.get("provenance", {})

    steps = [
        _step(
            "command",
            1,
            "Establish current operating status",
            "Identify connected systems, current work, attention and snapshot freshness.",
            "command",
            "dashboard",
            bool(snapshot),
            None if snapshot else "The canonical dashboard snapshot is unavailable.",
            [
                _evidence(
                    "dashboard_snapshot",
                    provenance.get("source_identity", "mission-control/dashboard"),
                    None,
                )
            ],
        ),
        _step(
            "workflow",
            2,
            "Follow active work to its current leaf",
            "Open the stage map and identify the leaf task, owner, machine, heartbeat and blocker.",
            "workflows",
            workflow.get("instance_id") if workflow else None,
            workflow is not None,
            None if workflow else "No active canonical workflow instance is available.",
            _workflow_evidence(workflow),
        ),
        _step(
            "agent",
            3,
            "Inspect the responsible agent",
            "Confirm current assignment, recent history, capabilities and bounded authority.",
            "agents",
            agent.get("id") if agent else None,
            agent is not None,
            None
            if agent
            else "The selected workflow has no canonically linked responsible agent.",
            [_evidence("agent", agent.get("id"), None)] if agent else [],
        ),
        _step(
            "backtest",
            4,
            "Inspect a terminal native backtest",
            "Verify the actual universe, window, costs, OOS gates and terminal BT-009 receipt.",
            "research",
            backtest.get("task_id") if backtest else None,
            backtest is not None,
            None
            if backtest
            else "No terminal native BT-009 receipt is available; task success is not substituted.",
            _backtest_evidence(backtest),
        ),
        _step(
            "venue",
            5,
            "Trace a Bybit demo order lifecycle",
            "Follow decision, venue-confirmed fill and reconciliation, then copy the venue order ID.",
            "execution",
            _event_key(demo_event) if demo_event else None,
            demo_event is not None,
            None
            if demo_event
            else "No complete Bybit demo decision-to-fill-to-reconciliation trace is published.",
            _event_evidence(demo_event),
        ),
    ]
    digest_payload = {"steps": steps, "source_generated_at": provenance.get("generated_at")}
    walkthrough_digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    ready = sum(item["status"] == "ready" for item in steps)
    return {
        "schema_version": "mission-control-investor-walkthrough-v1",
        "generated_at": observed_at.isoformat(),
        "walkthrough_digest": walkthrough_digest,
        "status": "ready" if ready == len(steps) else "incomplete",
        "ready_steps": ready,
        "total_steps": len(steps),
        "steps": steps,
        "claim_boundary": (
            "This walkthrough links only records present in current canonical projections. "
            "Unavailable evidence remains unavailable; completing the walkthrough grants no "
            "research, promotion, capital, or order authority."
        ),
    }


def _step(
    step_id: str,
    ordinal: int,
    title: str,
    prompt: str,
    view: str,
    entity_id: str | None,
    available: bool,
    unavailable_reason: str | None,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": step_id,
        "ordinal": ordinal,
        "title": title,
        "prompt": prompt,
        "view": view,
        "entity_id": entity_id,
        "status": "ready" if available else "unavailable",
        "unavailable_reason": unavailable_reason,
        "evidence": evidence,
    }


def _evidence(kind: str, identity: Any, digest: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "identity": str(identity) if identity else None,
        "digest": digest if isinstance(digest, str) else None,
    }


def _select_workflow(items: Any) -> dict[str, Any] | None:
    candidates = [
        item
        for item in items
        if isinstance(item, dict) and item.get("state") in _ACTIVE_WORKFLOW_STATES
    ]
    candidates.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    candidates.sort(key=lambda item: item.get("current_leaf") is None)
    return candidates[0] if candidates else None


def _workflow_evidence(workflow: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not workflow:
        return []
    entry = workflow.get("entry_evidence", {})
    exit_evidence = workflow.get("exit_evidence", {})
    evidence = [_evidence("workflow_instance", workflow.get("instance_id"), entry.get("digest"))]
    if exit_evidence.get("digest"):
        evidence.append(_evidence("workflow_exit", workflow.get("instance_id"), exit_evidence["digest"]))
    return evidence


def _select_responsible_agent(
    snapshot: dict[str, Any], workflow: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not workflow:
        return None
    leaf_id = str((workflow.get("current_leaf") or {}).get("id") or "")
    owner = workflow.get("owner") or {}
    tasks = [item for item in snapshot.get("tasks", []) if isinstance(item, dict)]
    task = next((item for item in tasks if str(item.get("id")) == leaf_id), None)
    agent_id = (task or {}).get("assigned_agent_id")
    if not agent_id and owner.get("type") == "agent":
        agent_id = owner.get("id")
    if not agent_id:
        return None
    return next(
        (
            item
            for item in snapshot.get("agents", [])
            if isinstance(item, dict) and str(item.get("id")) == str(agent_id)
        ),
        None,
    )


def _select_terminal_backtest(activity: Any) -> dict[str, Any] | None:
    items = activity.get("items", []) if isinstance(activity, dict) else []
    candidates = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("status") in _TERMINAL_BACKTEST_STATES
        and item.get("execution_evidence") == "native_terminal_receipt"
        and isinstance(item.get("terminal_receipt"), dict)
        and item["terminal_receipt"].get("present") is True
        and item["terminal_receipt"].get("digest")
    ]
    candidates.sort(
        key=lambda item: str(
            item.get("ended_at") or item.get("updated_at") or item.get("window_end") or ""
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _backtest_evidence(backtest: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not backtest:
        return []
    receipt = backtest.get("terminal_receipt", {})
    return [
        _evidence("bt009_terminal_receipt", backtest.get("task_id"), receipt.get("digest")),
        *[
            _evidence("artifact", artifact.get("id"), artifact.get("sha256"))
            for artifact in backtest.get("artifacts", [])
            if isinstance(artifact, dict)
        ],
    ]


def _select_demo_event(events: Any) -> dict[str, Any] | None:
    eligible = [
        item
        for item in events
        if isinstance(item, dict)
        and item.get("venue") == "bybit"
        and item.get("environment") == "demo"
    ]
    for fill in reversed(eligible):
        if fill.get("event_type") not in _FILL_EVENTS:
            continue
        related = [item for item in eligible if _events_related(fill, item)]
        types = {item.get("event_type") for item in related}
        if types & _DECISION_EVENTS and types & _RECONCILIATION_EVENTS:
            return fill
    return None


def _events_related(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if any(
        left.get(field) != right.get(field)
        for field in ("venue", "environment", "account_pseudonym")
    ):
        return False
    fields = ("correlation_id", "client_order_id", "venue_order_id", "execution_id")
    left_ids = {left.get(field) for field in fields if left.get(field)}
    right_ids = {right.get(field) for field in fields if right.get(field)}
    return bool(left_ids & right_ids)


def _event_key(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    return (event.get("evidence") or {}).get("event_digest") or event.get("event_id")


def _event_evidence(event: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not event:
        return []
    evidence = event.get("evidence") or {}
    return [
        _evidence("venue_event", _event_key(event), evidence.get("event_digest")),
        _evidence("exec011_receipt", event.get("venue_order_id"), evidence.get("receipt_digest")),
    ]


class WalkthroughJournal:
    """Bounded, Mac-local usability journal. It is not canonical system evidence."""

    def __init__(self, path: Path, *, capacity: int = 100) -> None:
        self.path = path
        self.capacity = capacity
        self._lock = threading.Lock()

    def start(self, walkthrough_digest: str, ready_steps: int, total_steps: int) -> dict[str, Any]:
        with self._lock:
            sessions = self._read()
            session = {
                "id": str(uuid4()),
                "walkthrough_digest": walkthrough_digest,
                "status": "in_progress",
                "started_at": _now(),
                "completed_at": None,
                "elapsed_ms": None,
                "ready_steps": ready_steps,
                "total_steps": total_steps,
                "observations": [],
                "summary": None,
            }
            sessions.append(session)
            self._write(sessions[-self.capacity :])
            return session

    def observe(self, session_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            sessions = self._read()
            session = self._find(sessions, session_id)
            if session["status"] != "in_progress":
                raise ValueError("The rehearsal session is already terminal.")
            if len(session["observations"]) >= 250:
                raise ValueError("The rehearsal observation limit was reached.")
            event = {"sequence": len(session["observations"]) + 1, "recorded_at": _now(), **observation}
            session["observations"].append(event)
            self._write(sessions)
            return event

    def finish(
        self, session_id: str, *, status: str, elapsed_ms: int, summary: str | None
    ) -> dict[str, Any]:
        with self._lock:
            sessions = self._read()
            session = self._find(sessions, session_id)
            if session["status"] != "in_progress":
                raise ValueError("The rehearsal session is already terminal.")
            session.update(
                status=status,
                elapsed_ms=elapsed_ms,
                summary=summary,
                completed_at=_now(),
            )
            self._write(sessions)
            return session

    def recent(self, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._read()[-limit:]))

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise TypeError("The rehearsal journal is invalid.")
        return payload

    def _write(self, sessions: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary_path = handle.name
                json.dump(sessions, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @staticmethod
    def _find(sessions: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if session is None:
            raise KeyError(session_id)
        return session


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
