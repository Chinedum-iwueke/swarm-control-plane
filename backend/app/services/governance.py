import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalEvent, EngineeringMission, Task, TaskApproval


def task_plan_digest(document: dict) -> str:
    canonical = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def append_approval_event(
    db: Session,
    approval: TaskApproval,
    event_type: str,
    actor: str,
    reason: str,
    payload: dict | None = None,
) -> ApprovalEvent:
    event = ApprovalEvent(
        approval_id=approval.id,
        event_type=event_type,
        actor=actor,
        reason=reason,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event


def create_approval(db: Session, task: Task) -> TaskApproval:
    approval = TaskApproval(
        task_id=task.id,
        status="pending",
        plan_digest=task.plan_digest,
        risk_level=task.risk_level,
        scope={
            "project": task.project,
            "task_type": task.task_type,
            "input_contract": task.input_contract,
        },
        requested_by=task.created_by,
    )
    db.add(approval)
    db.flush()
    requested = append_approval_event(
        db, approval, "approval_requested", task.created_by, "Task requires approval."
    )
    from app.services.founder_notifications import enqueue_approval_gate

    enqueue_approval_gate(db, approval, task, generation=requested.id)
    return approval


def approve_task(
    db: Session,
    approval: TaskApproval,
    *,
    actor: str,
    reason: str,
    expires_in_seconds: int,
) -> None:
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval is not pending.")
    task = db.get(Task, approval.task_id)
    if task is None or task.plan_digest != approval.plan_digest:
        raise HTTPException(status_code=409, detail="Task plan digest has changed.")
    now = datetime.now(UTC)
    nonce = secrets.token_urlsafe(32)
    approval.status = "approved"
    approval.decided_by = actor
    approval.decision_reason = reason
    approval.nonce_digest = hashlib.sha256(nonce.encode()).hexdigest()
    approval.issued_at = now
    approval.expires_at = now + timedelta(seconds=expires_in_seconds)
    approval.updated_at = now
    task.status = "queued"
    if task.mission_id is not None:
        mission = db.get(EngineeringMission, task.mission_id)
        if mission is not None and mission.supervision_enabled:
            mission.next_reconcile_at = now
    granted = append_approval_event(db, approval, "approval_granted", actor, reason)
    from app.services.founder_notifications import enqueue_task_ready
    from app.services.tasks import append_task_event

    append_task_event(
        db,
        task,
        "task_ready",
        "Approved task is ready for a matching worker.",
        payload={"approval_id": str(approval.id), "plan_digest": task.plan_digest},
    )
    enqueue_task_ready(db, task, approval, generation=granted.id)


def decide_task(
    db: Session,
    approval: TaskApproval,
    *,
    actor: str,
    reason: str,
    action: str,
) -> None:
    allowed = {"reject": {"pending"}, "revoke": {"approved"}}
    if approval.status not in allowed[action]:
        raise HTTPException(status_code=409, detail=f"Approval cannot be {action}d.")
    now = datetime.now(UTC)
    approval.status = "rejected" if action == "reject" else "revoked"
    approval.decided_by = actor
    approval.decision_reason = reason
    approval.updated_at = now
    task = db.get(Task, approval.task_id)
    if task is not None:
        task.status = "cancelled" if action == "reject" else "pending_approval"
    append_approval_event(db, approval, f"approval_{approval.status}", actor, reason)


def consume_task_approval(db: Session, task: Task, now: datetime) -> None:
    if not task.approval_required:
        return
    approval = db.scalar(
        select(TaskApproval)
        .where(TaskApproval.task_id == task.id)
        .with_for_update()
    )
    if approval is None or approval.status != "approved":
        raise HTTPException(status_code=409, detail="Task lacks an approved plan.")
    if approval.expires_at is None or approval.expires_at <= now:
        approval.status = "expired"
        approval.updated_at = now
        task.status = "pending_approval"
        append_approval_event(
            db, approval, "approval_expired", "control-plane", "Approval expired."
        )
        raise HTTPException(status_code=409, detail="Task approval expired.")
    approval.status = "consumed"
    approval.consumed_at = now
    approval.updated_at = now
    append_approval_event(
        db,
        approval,
        "approval_consumed",
        "control-plane",
        "Approval consumed by task lease.",
        {"attempt_number": task.attempt_count + 1},
    )


def expire_approvals(db: Session, now: datetime) -> int:
    approvals = db.scalars(
        select(TaskApproval)
        .where(
            TaskApproval.status == "approved",
            TaskApproval.expires_at.is_not(None),
            TaskApproval.expires_at <= now,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for approval in approvals:
        approval.status = "expired"
        approval.updated_at = now
        task = db.get(Task, approval.task_id)
        if task is not None and task.status == "queued":
            task.status = "pending_approval"
        append_approval_event(
            db, approval, "approval_expired", "control-plane", "Approval expired."
        )
    return len(approvals)


def rearm_task_approval(db: Session, task: Task, reason: str) -> None:
    if not task.approval_required:
        task.status = "queued"
        return
    approval = db.scalar(
        select(TaskApproval)
        .where(TaskApproval.task_id == task.id)
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=409, detail="Task approval is missing.")
    approval.status = "pending"
    approval.decided_by = None
    approval.decision_reason = None
    approval.nonce_digest = None
    approval.issued_at = None
    approval.expires_at = None
    approval.consumed_at = None
    approval.updated_at = datetime.now(UTC)
    task.status = "pending_approval"
    append_approval_event(
        db,
        approval,
        "approval_requested",
        "control-plane",
        reason,
        {"attempt_count": task.attempt_count},
    )
