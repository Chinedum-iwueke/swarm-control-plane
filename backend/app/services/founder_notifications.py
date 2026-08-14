from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ApprovalEvent,
    EngineeringMission,
    FounderNotification,
    Task,
    TaskApproval,
    TaskDependency,
)


def approval_readiness(
    db: Session, approval: TaskApproval
) -> tuple[bool, list[str], Task, EngineeringMission | None]:
    task = db.get(Task, approval.task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="Approval task is unavailable.")
    dependencies = db.execute(
        select(Task.task_number, Task.status)
        .join(TaskDependency, Task.id == TaskDependency.depends_on_task_id)
        .where(TaskDependency.task_id == task.id)
    ).all()
    blocked_by = [
        f"{number}:{state}"
        for number, state in dependencies
        if state != "succeeded"
    ]
    mission = db.get(EngineeringMission, task.mission_id) if task.mission_id else None
    now = datetime.now(UTC)
    mission_ready = mission is None or (
        mission.status == "active" and mission.deadline_at > now
    )
    return (
        approval.status == "pending"
        and task.status == "pending_approval"
        and not blocked_by
        and mission_ready,
        blocked_by,
        task,
        mission,
    )


def reconcile_founder_notifications(db: Session) -> list[FounderNotification]:
    now = datetime.now(UTC)
    approvals = db.scalars(
        select(TaskApproval).where(TaskApproval.status == "pending")
    ).all()
    current_keys: set[str] = set()
    for approval in approvals:
        actionable, blocked_by, task, _ = approval_readiness(db, approval)
        requested = db.scalar(
            select(ApprovalEvent)
            .where(
                ApprovalEvent.approval_id == approval.id,
                ApprovalEvent.event_type == "approval_requested",
            )
            .order_by(ApprovalEvent.id.desc())
            .limit(1)
        )
        generation = requested.id if requested is not None else 0
        key = f"approval:{approval.id}:{approval.plan_digest}:{generation}"
        current_keys.add(key)
        notification = _insert_once(
            db,
            FounderNotification(
                kind="approval_required",
                entity_id=approval.id,
                deduplication_key=key,
                state="waiting",
                payload={
                    "approval_id": str(approval.id),
                    "task_number": task.task_number,
                    "task_title": task.title,
                    "operation": (task.input_contract or {}).get("operation"),
                    "task_type": task.task_type,
                    "risk_level": approval.risk_level,
                    "plan_digest": approval.plan_digest,
                    "blocked_by": blocked_by,
                },
            ),
        )
        desired_state = "pending" if actionable else "waiting"
        if notification.state in {"pending", "waiting"}:
            notification.state = desired_state
            notification.updated_at = now

    missions = db.scalars(
        select(EngineeringMission).where(
            EngineeringMission.supervision_enabled.is_(True),
            EngineeringMission.supervision_status == "pending_approval",
        )
    ).all()
    for mission in missions:
        key = f"mission:{mission.id}:{mission.manifest_digest}"
        current_keys.add(key)
        _insert_once(
            db,
            FounderNotification(
                kind="mission_approval_required",
                entity_id=mission.id,
                deduplication_key=key,
                state="pending",
                payload={
                    "mission_id": str(mission.id),
                    "milestone_id": mission.milestone_id,
                    "objective": mission.objective,
                    "manifest_digest": mission.manifest_digest,
                    "max_auto_recoveries": (mission.supervision_policy or {}).get(
                        "max_auto_recoveries", 0
                    ),
                },
            ),
        )

    pending = db.scalars(
        select(FounderNotification).where(
            FounderNotification.state.in_(["pending", "waiting"]),
            FounderNotification.kind.in_(
                ["approval_required", "mission_approval_required"]
            ),
        )
    ).all()
    for notification in pending:
        if notification.deduplication_key not in current_keys:
            notification.state = "superseded"
            notification.superseded_at = now
            notification.updated_at = now

    ready_notifications = db.scalars(
        select(FounderNotification).where(
            FounderNotification.state == "pending",
            FounderNotification.kind == "task_ready",
        )
    ).all()
    for notification in ready_notifications:
        task = db.get(Task, notification.entity_id)
        if task is None or task.status != "queued":
            notification.state = "superseded"
            notification.superseded_at = now
            notification.updated_at = now

    db.flush()
    return list(
        db.scalars(
            select(FounderNotification)
            .where(FounderNotification.state == "pending")
            .order_by(FounderNotification.created_at, FounderNotification.id)
        ).all()
    )


def enqueue_approval_gate(
    db: Session,
    approval: TaskApproval,
    task: Task,
    *,
    generation: int,
) -> FounderNotification:
    return _insert_once(
        db,
        FounderNotification(
            kind="approval_required",
            entity_id=approval.id,
            deduplication_key=(
                f"approval:{approval.id}:{approval.plan_digest}:{generation}"
            ),
            state="waiting",
            payload={
                "approval_id": str(approval.id),
                "task_number": task.task_number,
                "task_title": task.title,
                "operation": (task.input_contract or {}).get("operation"),
                "task_type": task.task_type,
                "risk_level": approval.risk_level,
                "plan_digest": approval.plan_digest,
                "blocked_by": [],
            },
        ),
    )


def enqueue_task_ready(
    db: Session,
    task: Task,
    approval: TaskApproval,
    *,
    generation: int,
) -> FounderNotification:
    notification = FounderNotification(
        kind="task_ready",
        entity_id=task.id,
        deduplication_key=f"task-ready:{task.id}:{approval.id}:{generation}",
        state="pending",
        payload={
            "task_id": str(task.id),
            "task_number": task.task_number,
            "task_title": task.title,
            "task_type": task.task_type,
            "plan_digest": task.plan_digest,
        },
    )
    return _insert_once(db, notification)


def acknowledge_notification(
    notification: FounderNotification, delivery_reference: str
) -> None:
    if notification.state == "acknowledged":
        return
    if notification.state != "pending":
        raise HTTPException(status_code=409, detail="Notification is no longer active.")
    now = datetime.now(UTC)
    notification.state = "acknowledged"
    notification.acknowledged_by = delivery_reference
    notification.acknowledged_at = now
    notification.updated_at = now


def _insert_once(
    db: Session, notification: FounderNotification
) -> FounderNotification:
    existing = db.scalar(
        select(FounderNotification).where(
            FounderNotification.deduplication_key == notification.deduplication_key
        )
    )
    if existing is not None:
        return existing
    try:
        with db.begin_nested():
            db.add(notification)
            db.flush()
        return notification
    except IntegrityError:
        return db.scalar(
            select(FounderNotification).where(
                FounderNotification.deduplication_key
                == notification.deduplication_key
            )
        )
