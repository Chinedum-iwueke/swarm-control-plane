from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.operation import Operation, OperationEvent
from app.models.task import Task
from app.schemas.operation import OperationWrite

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
ACTIVE_STATES = frozenset(
    {"queued", "waiting_approval", "running", "blocked", "stalled"}
)


class OperationReporter:
    """Commit operation heartbeats independently from the workload transaction."""

    def __init__(self, payload: OperationWrite, actor: str) -> None:
        self.payload = payload
        self.actor = actor

    def start(self) -> None:
        self._write(self.payload, "started")

    def progress(
        self,
        phase: str,
        current: int | None = None,
        total: int | None = None,
        unit: str | None = None,
    ) -> None:
        self.payload = self.payload.model_copy(
            update={
                "state": "running",
                "phase": phase,
                "progress_mode": "determinate"
                if total is not None
                else "indeterminate",
                "progress_current": current if total is not None else None,
                "progress_total": total,
                "progress_unit": unit if total is not None else None,
                "error_summary": None,
            }
        )
        self._write(self.payload, "progress")

    def succeed(self, *, detail: dict | None = None) -> None:
        updates: dict[str, Any] = {
            "state": "succeeded",
            "phase": "complete",
            "error_summary": None,
        }
        if self.payload.progress_total is not None:
            updates["progress_current"] = self.payload.progress_total
        if detail is not None:
            updates["detail"] = {**self.payload.detail, **detail}
        self.payload = self.payload.model_copy(update=updates)
        self._write(self.payload, "succeeded")

    def fail(self, exc: Exception) -> None:
        self.payload = self.payload.model_copy(
            update={
                "state": "failed",
                "phase": "failed",
                "error_summary": f"{type(exc).__name__}: {str(exc)[:3900]}",
                "retryable": True,
            }
        )
        self._write(self.payload, "failed")

    def _write(self, payload: OperationWrite, event_type: str) -> None:
        with SessionLocal() as session:
            upsert_operation(session, payload, actor=self.actor, event_type=event_type)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def upsert_operation(
    db: Session,
    payload: OperationWrite,
    *,
    actor: str,
    event_type: str = "progress",
    now: datetime | None = None,
    commit: bool = True,
) -> Operation:
    observed_at = now or datetime.now(UTC)
    operation = db.scalar(
        select(Operation).where(Operation.operation_key == payload.operation_key)
    )
    previous = None
    if operation is None:
        operation = Operation(
            operation_key=payload.operation_key,
            kind=payload.kind,
            title=payload.title,
            project=payload.project,
            machine=payload.machine,
            owner_type=payload.owner_type,
            owner_id=payload.owner_id,
            state=payload.state,
            phase=payload.phase,
            progress_mode=payload.progress_mode,
            progress_current=payload.progress_current,
            progress_total=payload.progress_total,
            progress_unit=payload.progress_unit,
            heartbeat_at=observed_at,
            started_at=observed_at if payload.state == "running" else None,
            completed_at=observed_at if payload.state in TERMINAL_STATES else None,
            cancellable=payload.cancellable,
            retryable=payload.retryable,
            error_summary=payload.error_summary,
            links=payload.links,
            detail=payload.detail,
            input_digest=payload.input_digest,
            record_digest="0" * 64,
        )
        db.add(operation)
        db.flush()
        event_type = "created"
    else:
        previous = (
            operation.state,
            operation.phase,
            operation.progress_current,
            operation.progress_total,
            operation.error_summary,
        )
        operation.kind = payload.kind
        operation.title = payload.title
        operation.project = payload.project
        operation.machine = payload.machine
        operation.owner_type = payload.owner_type
        operation.owner_id = payload.owner_id
        operation.state = payload.state
        operation.phase = payload.phase
        operation.progress_mode = payload.progress_mode
        operation.progress_current = payload.progress_current
        operation.progress_total = payload.progress_total
        operation.progress_unit = payload.progress_unit
        operation.cancellable = payload.cancellable
        operation.retryable = payload.retryable
        operation.error_summary = payload.error_summary
        operation.links = payload.links
        operation.detail = payload.detail
        operation.input_digest = payload.input_digest
        if operation.started_at is None and payload.state == "running":
            operation.started_at = observed_at
        if payload.state in TERMINAL_STATES and operation.completed_at is None:
            operation.completed_at = observed_at
    operation.heartbeat_at = observed_at
    operation.record_digest = _operation_digest(operation)
    current = (
        operation.state,
        operation.phase,
        operation.progress_current,
        operation.progress_total,
        operation.error_summary,
    )
    if previous != current:
        _append_event(db, operation, event_type, actor, observed_at)
    if commit:
        db.commit()
        db.refresh(operation)
    return operation


def reconcile_task_operations(
    db: Session, *, now: datetime | None = None, stall_after_seconds: int = 180
) -> int:
    observed_at = now or datetime.now(UTC)
    tasks = list(db.scalars(select(Task).order_by(Task.created_at)).all())
    changed = 0
    for task in tasks:
        state, phase = _task_state(task, observed_at, stall_after_seconds)
        machine = task.allowed_machines[0] if len(task.allowed_machines) == 1 else None
        progress_current = 1 if state in TERMINAL_STATES else None
        progress_total = 1 if state in TERMINAL_STATES else None
        payload = OperationWrite(
            operation_key=f"task:{task.id}",
            kind=task.task_type,
            title=task.title,
            project=task.project,
            machine=machine,
            owner_type="task",
            owner_id=str(task.id),
            state=state,
            phase=phase,
            progress_mode="determinate"
            if state in TERMINAL_STATES
            else "indeterminate",
            progress_current=progress_current,
            progress_total=progress_total,
            progress_unit="task" if state in TERMINAL_STATES else None,
            retryable=state == "failed" and task.attempt_count < task.max_attempts,
            error_summary=_task_error(task),
            links={
                "task_id": str(task.id),
                "task_number": task.task_number,
                **({"mission_id": str(task.mission_id)} if task.mission_id else {}),
            },
            detail={
                "attempt": task.attempt_count,
                "max_attempts": task.max_attempts,
                "required_capabilities": task.required_capabilities,
            },
            input_digest=task.plan_digest,
        )
        before = db.scalar(
            select(Operation.record_digest).where(
                Operation.operation_key == payload.operation_key
            )
        )
        operation = upsert_operation(
            db,
            payload,
            actor="operation-reconciler",
            event_type="reconciled",
            now=observed_at,
            commit=False,
        )
        changed += int(before != operation.record_digest)
    db.commit()
    return changed


def mark_stalled_operations(
    db: Session, *, now: datetime | None = None, stall_after_seconds: int = 180
) -> int:
    observed_at = now or datetime.now(UTC)
    cutoff = observed_at - timedelta(seconds=stall_after_seconds)
    operations = list(
        db.scalars(
            select(Operation).where(
                Operation.state == "running", Operation.heartbeat_at < cutoff
            )
        ).all()
    )
    for operation in operations:
        payload = OperationWrite(
            operation_key=operation.operation_key,
            kind=operation.kind,
            title=operation.title,
            project=operation.project,
            machine=operation.machine,
            owner_type=operation.owner_type,
            owner_id=operation.owner_id,
            state="stalled",
            phase=operation.phase,
            progress_mode=operation.progress_mode,
            progress_current=operation.progress_current,
            progress_total=operation.progress_total,
            progress_unit=operation.progress_unit,
            cancellable=operation.cancellable,
            retryable=operation.retryable,
            error_summary="Operation heartbeat is stale.",
            links=operation.links,
            detail={**operation.detail, "stalled_after_seconds": stall_after_seconds},
            input_digest=operation.input_digest,
        )
        upsert_operation(
            db,
            payload,
            actor="operation-reconciler",
            event_type="stalled",
            now=observed_at,
            commit=False,
        )
    db.commit()
    return len(operations)


def operation_summary(db: Session) -> dict[str, Any]:
    reconcile_task_operations(db)
    mark_stalled_operations(db)
    counts = dict(
        db.execute(
            select(Operation.state, func.count()).group_by(Operation.state)
        ).all()
    )
    return {
        "generated_at": datetime.now(UTC),
        "counts": counts,
        "active_total": sum(counts.get(state, 0) for state in ACTIVE_STATES),
        "terminal_total": sum(counts.get(state, 0) for state in TERMINAL_STATES),
    }


def _task_state(task: Task, now: datetime, stall_after_seconds: int) -> tuple[str, str]:
    status = task.status
    if status == "pending_approval":
        return "waiting_approval", "approval"
    if status in {"queued", "pending", "leaseable"}:
        return "queued", "queued"
    if status in {"leased", "running", "in_progress", "executing"}:
        heartbeat = (
            task.last_execution_heartbeat_at or task.started_at or task.leased_at
        )
        if heartbeat is not None and heartbeat < now - timedelta(
            seconds=stall_after_seconds
        ):
            return "stalled", "execution"
        return "running", "execution"
    if status in {"succeeded", "complete", "completed"}:
        return "succeeded", "complete"
    if status == "failed":
        return "failed", "failed"
    if status in {"cancelled", "canceled", "rejected", "expired"}:
        return "cancelled", status
    return "blocked", status


def _task_error(task: Task) -> str | None:
    if task.status != "failed":
        return None
    failure = task.failure or {}
    return str(
        failure.get("message") or failure.get("error_category") or "Task failed."
    )[:4000]


def _operation_digest(operation: Operation) -> str:
    return canonical_digest(
        {
            "operation_key": operation.operation_key,
            "kind": operation.kind,
            "title": operation.title,
            "project": operation.project,
            "machine": operation.machine,
            "owner_type": operation.owner_type,
            "owner_id": operation.owner_id,
            "state": operation.state,
            "phase": operation.phase,
            "progress_mode": operation.progress_mode,
            "progress_current": operation.progress_current,
            "progress_total": operation.progress_total,
            "progress_unit": operation.progress_unit,
            "cancellable": operation.cancellable,
            "retryable": operation.retryable,
            "error_summary": operation.error_summary,
            "links": operation.links,
            "detail": operation.detail,
            "input_digest": operation.input_digest,
        }
    )


def _append_event(
    db: Session, operation: Operation, event_type: str, actor: str, now: datetime
) -> None:
    sequence = (
        int(
            db.scalar(
                select(func.coalesce(func.max(OperationEvent.sequence), 0)).where(
                    OperationEvent.operation_id == operation.id
                )
            )
            or 0
        )
        + 1
    )
    detail = {
        "progress_mode": operation.progress_mode,
        "progress_current": operation.progress_current,
        "progress_total": operation.progress_total,
        "progress_unit": operation.progress_unit,
        "error_summary": operation.error_summary,
    }
    digest = canonical_digest(
        {
            "operation_id": str(operation.id),
            "sequence": sequence,
            "event_type": event_type,
            "state": operation.state,
            "phase": operation.phase,
            "actor": actor,
            "detail": detail,
            "created_at": now.isoformat(),
        }
    )
    db.add(
        OperationEvent(
            operation_id=operation.id,
            sequence=sequence,
            event_type=event_type,
            state=operation.state,
            phase=operation.phase,
            actor=actor,
            detail=detail,
            record_digest=digest,
            created_at=now,
        )
    )
