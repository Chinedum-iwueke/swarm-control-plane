from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EngineeringMission, Task
from app.services.governance import rearm_task_approval
from app.services.missions import append_mission_event, refresh_mission
from app.services.tasks import append_task_event, reap_expired_leases


def approve_supervision(
    db: Session,
    mission: EngineeringMission,
    *,
    actor: str,
    reason: str,
) -> None:
    if not mission.supervision_enabled:
        raise HTTPException(status_code=409, detail="Mission is not supervised.")
    if mission.supervision_status != "pending_approval":
        raise HTTPException(
            status_code=409, detail="Mission plan is not pending approval."
        )
    if mission.manifest_digest != _current_manifest_digest(mission):
        raise HTTPException(
            status_code=409, detail="Mission manifest digest has changed."
        )
    now = datetime.now(UTC)
    mission.status = "active"
    mission.supervision_status = "active"
    mission.supervision_approved_at = now
    mission.supervision_approved_by = actor
    mission.next_reconcile_at = now
    append_mission_event(
        db,
        mission,
        "mission_supervision_approved",
        actor,
        reason,
        {"manifest_digest": mission.manifest_digest},
    )


def abort_supervision(
    db: Session,
    mission: EngineeringMission,
    *,
    actor: str,
    reason: str,
) -> None:
    if not mission.supervision_enabled:
        raise HTTPException(status_code=409, detail="Mission is not supervised.")
    tasks = db.scalars(
        select(Task).where(Task.mission_id == mission.id).with_for_update()
    ).all()
    if any(task.status in {"leased", "running"} for task in tasks):
        raise HTTPException(
            status_code=409,
            detail="Running mission checkpoints must stop before abort.",
        )
    now = datetime.now(UTC)
    for task in tasks:
        if task.status in {"queued", "pending_approval", "failed"}:
            task.status = "cancelled"
            task.completed_at = now
            append_task_event(
                db,
                task,
                "task_cancelled",
                "Task cancelled by supervised mission abort.",
                payload={"actor": actor, "reason": reason},
            )
    mission.status = "cancelled"
    mission.supervision_status = "aborted"
    mission.supervision_exception = {
        "category": "operator_abort",
        "reason": reason,
    }
    mission.next_reconcile_at = None
    mission.completed_at = now
    append_mission_event(
        db,
        mission,
        "mission_supervision_aborted",
        actor,
        reason,
        {"manifest_digest": mission.manifest_digest},
    )


def reconcile_mission(
    db: Session,
    mission: EngineeringMission,
) -> tuple[str, UUID | None]:
    if not mission.supervision_enabled:
        raise HTTPException(status_code=409, detail="Mission is not supervised.")
    if mission.supervision_status == "pending_approval":
        return "waiting_approval", None
    if mission.supervision_status == "attention_required":
        return "attention_required", None
    if mission.supervision_status not in {"active", "recovering"}:
        return "waiting", None

    now = datetime.now(UTC)
    if mission.next_reconcile_at is not None and mission.next_reconcile_at > now:
        return "waiting", None

    reap_expired_leases(db)
    refresh_mission(db, mission.id)
    tasks = db.scalars(
        select(Task).where(Task.mission_id == mission.id).order_by(Task.created_at)
    ).all()
    if tasks and all(task.status == "succeeded" for task in tasks):
        mission.supervision_status = "succeeded"
        mission.status = "succeeded"
        mission.completed_at = now
        append_mission_event(
            db,
            mission,
            "mission_supervision_completed",
            "mission-supervisor",
            "All mission checkpoints completed.",
        )
        return "succeeded", None

    if mission.deadline_at <= now:
        mission.status = "blocked"
        mission.supervision_status = "attention_required"
        mission.supervision_exception = {
            "category": "mission_deadline_exhausted",
            "retryable": False,
            "time_budget_available": False,
        }
        mission.next_reconcile_at = None
        append_mission_event(
            db,
            mission,
            "mission_attention_required",
            "mission-supervisor",
            "Mission time budget was exhausted.",
            mission.supervision_exception,
        )
        return "attention_required", None

    failed = next((task for task in tasks if task.status == "failed"), None)
    if failed is None:
        mission.next_reconcile_at = now + timedelta(seconds=10)
        return "waiting", None

    policy = mission.supervision_policy or {}
    category = str(
        failed.failure.get("error_category")
        or failed.failure.get("reason")
        or "unknown"
    )
    retryable = bool(failed.failure.get("retryable")) or category in set(
        policy.get("retryable_categories", [])
    )
    max_recoveries = int(policy.get("max_auto_recoveries", 0))
    within_attempt_budget = failed.attempt_count < failed.max_attempts
    within_time_budget = mission.deadline_at > now
    if (
        retryable
        and mission.recovery_count < max_recoveries
        and within_attempt_budget
        and within_time_budget
    ):
        mission.recovery_count += 1
        mission.status = "active"
        mission.supervision_status = "recovering"
        mission.supervision_exception = {}
        failed.completed_at = None
        failed.result = {}
        rearm_task_approval(
            db, failed, "Mission supervisor authorized bounded recovery."
        )
        append_task_event(
            db,
            failed,
            "task_auto_recovered",
            "Mission supervisor resumed a retryable checkpoint.",
            payload={"category": category, "recovery_count": mission.recovery_count},
        )
        backoff = int(policy.get("retry_backoff_seconds", 30))
        mission.next_reconcile_at = now + timedelta(seconds=backoff)
        append_mission_event(
            db,
            mission,
            "mission_auto_recovered",
            "mission-supervisor",
            "Retryable checkpoint resumed within approved mission budget.",
            {"task_id": str(failed.id), "category": category},
        )
        return "recovered", failed.id

    exception = {
        "category": category,
        "task_id": str(failed.id),
        "task_number": failed.task_number,
        "retryable": retryable,
        "attempt_budget_available": within_attempt_budget,
        "time_budget_available": within_time_budget,
        "recovery_budget_available": mission.recovery_count < max_recoveries,
    }
    mission.status = "blocked"
    mission.supervision_status = "attention_required"
    mission.supervision_exception = exception
    mission.next_reconcile_at = None
    append_mission_event(
        db,
        mission,
        "mission_attention_required",
        "mission-supervisor",
        "Mission authority is exhausted or the failure is not retryable.",
        exception,
    )
    return "attention_required", failed.id


def _current_manifest_digest(mission: EngineeringMission) -> str:
    import hashlib
    import json

    canonical = json.dumps(
        mission.manifest,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
