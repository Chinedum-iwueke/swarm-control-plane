import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EngineeringMission, MissionEvent, Task, TaskDependency
from app.schemas.mission import EngineeringMilestoneManifest
from app.services.governance import task_plan_digest
from app.services.tasks import append_task_event


def canonical_manifest(manifest: EngineeringMilestoneManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def create_mission(
    db: Session,
    manifest: EngineeringMilestoneManifest,
    created_by: str,
    approval_signature: str,
) -> EngineeringMission:
    digest = hashlib.sha256(canonical_manifest(manifest)).hexdigest()
    mission = EngineeringMission(
        milestone_id=manifest.milestone_id,
        project=manifest.project,
        objective=manifest.objective,
        status="active",
        manifest_digest=digest,
        manifest=manifest.model_dump(mode="json"),
        approved_by=manifest.approved_by,
        approval_reference=manifest.approval_reference,
        approval_signature=approval_signature,
        max_tasks=manifest.budget.max_tasks,
        max_attempts=manifest.budget.max_attempts_per_task,
        max_duration_seconds=manifest.budget.max_duration_seconds,
        deadline_at=datetime.now(UTC)
        + timedelta(seconds=manifest.budget.max_duration_seconds),
        created_by=created_by,
    )
    db.add(mission)
    db.flush()
    append_mission_event(
        db,
        mission,
        "mission_created",
        created_by,
        "Approved engineering mission created.",
        {"manifest_digest": digest},
    )
    tasks_by_step: dict[str, Task] = {}
    for index, item in enumerate(manifest.work_items, start=1):
        contract = {
            "repository": manifest.project,
            "workflow": manifest.workflow,
            "base_ref": manifest.base_ref,
            "milestone_id": manifest.milestone_id,
            "work_item_id": item.id,
            "objective": item.objective,
            "allowed_paths": item.allowed_paths,
            "context_paths": item.context_paths,
            "acceptance_criteria": item.acceptance_criteria,
            "stop_conditions": item.stop_conditions,
            "max_files_changed": manifest.budget.max_files_changed,
            "max_diff_lines": manifest.budget.max_diff_lines,
            "max_duration_seconds": manifest.budget.max_duration_seconds,
        }
        task = Task(
            task_number=f"M4-{digest[:8]}-{index:02d}",
            project=manifest.project,
            task_type="engineering_mission",
            title=f"{manifest.milestone_id}: {item.id}",
            objective=item.objective,
            status="queued",
            priority=60,
            risk_level=manifest.risk_level,
            mission_id=mission.id,
            milestone_step_id=item.id,
            created_by=created_by,
            input_contract=contract,
            expected_outputs=["patch", "validation", "review", "pr_bundle"],
            acceptance_criteria=item.acceptance_criteria,
            approval_policy={
                "milestone_approval_reference": manifest.approval_reference,
                "approved_by": manifest.approved_by,
            },
            approval_required=False,
            plan_digest=task_plan_digest(contract),
            required_capabilities=manifest.required_capabilities,
            allowed_machines=manifest.allowed_machines,
            max_attempts=manifest.budget.max_attempts_per_task,
            attempt_count=0,
            result={},
            failure={},
        )
        db.add(task)
        db.flush()
        append_task_event(
            db,
            task,
            "task_created",
            "Task created from an approved engineering milestone.",
            payload={
                "created_by": created_by,
                "priority": task.priority,
                "risk_level": task.risk_level,
            },
        )
        append_task_event(
            db,
            task,
            "mission_task_planned",
            "Task created from approved milestone manifest.",
            payload={
                "mission_id": str(mission.id),
                "manifest_digest": digest,
                "work_item_id": item.id,
            },
        )
        tasks_by_step[item.id] = task
    for item in manifest.work_items:
        for dependency in item.depends_on:
            db.add(
                TaskDependency(
                    task_id=tasks_by_step[item.id].id,
                    depends_on_task_id=tasks_by_step[dependency].id,
                )
            )
    db.flush()
    return mission


def verify_mission_approval(
    manifest: EngineeringMilestoneManifest,
    approval_signature: str,
    approval_secret: str,
) -> None:
    expected = hmac.new(
        approval_secret.encode(), canonical_manifest(manifest), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, approval_signature):
        raise HTTPException(
            status_code=422, detail="Mission approval signature verification failed."
        )


def refresh_mission(db: Session, mission_id) -> None:
    mission = db.get(EngineeringMission, mission_id)
    if mission is None:
        return
    statuses = list(
        db.scalars(select(Task.status).where(Task.mission_id == mission.id)).all()
    )
    previous = mission.status
    all_succeeded = bool(statuses) and all(
        status == "succeeded" for status in statuses
    )
    if all_succeeded:
        mission.status = "succeeded"
        mission.completed_at = datetime.now(UTC)
    elif mission.deadline_at <= datetime.now(UTC) or any(
        status in {"failed", "cancelled"} for status in statuses
    ):
        mission.status = "blocked"
    else:
        mission.status = "active"
    if mission.status != previous and mission.status in {"succeeded", "blocked"}:
        append_mission_event(
            db,
            mission,
            f"mission_{mission.status}",
            "control-plane",
            f"Mission transitioned to {mission.status}.",
            {"task_statuses": statuses},
        )


def append_mission_event(
    db: Session,
    mission: EngineeringMission,
    event_type: str,
    actor: str,
    message: str,
    payload: dict | None = None,
) -> MissionEvent:
    event = MissionEvent(
        mission_id=mission.id,
        event_type=event_type,
        actor=actor,
        message=message,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event
