from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    ApprovalEvent,
    EngineeringMission,
    FounderNotification,
    Task,
    TaskApproval,
    TaskDependency,
)
from app.models.authority import AuthorityPolicySnapshot
from app.schemas.governance import ApprovalEventResponse, ApprovalResponse
from app.services.authority import canonical_digest


def approval_center_item(db: Session, approval: TaskApproval) -> dict:
    task = db.get(Task, approval.task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="Approval task is unavailable.")

    predecessor = aliased(Task)
    prerequisites = [
        {
            "task_id": str(task_id),
            "task_number": task_number,
            "title": title,
            "status": status,
            "satisfied": status == "succeeded",
        }
        for task_id, task_number, title, status in db.execute(
            select(
                predecessor.id,
                predecessor.task_number,
                predecessor.title,
                predecessor.status,
            )
            .join(
                TaskDependency,
                predecessor.id == TaskDependency.depends_on_task_id,
            )
            .where(TaskDependency.task_id == task.id)
            .order_by(predecessor.task_number)
        ).all()
    ]
    mission = db.get(EngineeringMission, task.mission_id) if task.mission_id else None
    now = datetime.now(UTC)
    mission_view = None
    mission_ready = True
    if mission is not None:
        mission_ready = mission.status == "active" and mission.deadline_at > now
        mission_view = {
            "id": str(mission.id),
            "milestone_id": mission.milestone_id,
            "status": mission.status,
            "deadline_at": mission.deadline_at.isoformat(),
            "ready": mission_ready,
        }

    current_scope = {
        "project": task.project,
        "task_type": task.task_type,
        "input_contract": task.input_contract,
    }
    changed_fields = sorted(
        key
        for key in sorted(set(approval.scope) | set(current_scope))
        if approval.scope.get(key) != current_scope.get(key)
    )
    current = approval.plan_digest == task.plan_digest and not changed_fields
    executable = bool(
        task.approval_required
        and task.status == "pending_approval"
        and approval.status == "pending"
        and current
    )
    blocked_by = [
        {
            "kind": "task_dependency",
            "reference": item["task_number"],
            "status": item["status"],
        }
        for item in prerequisites
        if not item["satisfied"]
    ]
    if not mission_ready:
        blocked_by.append(
            {
                "kind": "mission_state",
                "reference": mission.milestone_id if mission else "unknown",
                "status": mission.status if mission else "missing",
            }
        )
    if not current:
        blocked_by.append(
            {
                "kind": "digest_mismatch",
                "reference": task.task_number,
                "status": "superseded",
            }
        )

    notifications = list(
        db.scalars(
            select(FounderNotification)
            .where(
                FounderNotification.kind == "approval_required",
                FounderNotification.entity_id == approval.id,
                FounderNotification.state.in_(["pending", "waiting"]),
            )
            .order_by(FounderNotification.created_at.desc())
        ).all()
    )
    notification = notifications[0] if notifications else None
    notification_view = (
        {
            "id": str(notification.id),
            "state": notification.state,
            "deduplication_key": notification.deduplication_key,
            "created_at": notification.created_at.isoformat(),
        }
        if notification
        else None
    )
    policy = db.scalar(
        select(AuthorityPolicySnapshot).where(
            AuthorityPolicySnapshot.status == "active"
        )
    )
    policy_view = (
        {
            "id": str(policy.id),
            "version": policy.version,
            "manifest_digest": policy.manifest_digest,
        }
        if policy
        else None
    )
    events = list(
        db.scalars(
            select(ApprovalEvent)
            .where(ApprovalEvent.approval_id == approval.id)
            .order_by(ApprovalEvent.id)
        ).all()
    )
    task_view = {
        "id": str(task.id),
        "task_number": task.task_number,
        "title": task.title,
        "objective": task.objective,
        "project": task.project,
        "task_type": task.task_type,
        "status": task.status,
        "risk_level": task.risk_level,
        "plan_digest": task.plan_digest,
        "input_contract": task.input_contract,
        "acceptance_criteria": task.acceptance_criteria,
        "expected_outputs": task.expected_outputs,
        "required_capabilities": task.required_capabilities,
        "allowed_machines": task.allowed_machines,
        "max_attempts": task.max_attempts,
    }
    review_document = {
        "schema_version": "digest-safe-approval-review-v1.0.0",
        "approval_id": str(approval.id),
        "approval_status": approval.status,
        "approval_updated_at": approval.updated_at.isoformat(),
        "plan_digest": approval.plan_digest,
        "scope": approval.scope,
        "task": task_view,
        "current": current,
        "executable": executable,
        "prerequisites": prerequisites,
        "mission": mission_view,
        "authority_policy": policy_view,
        "notification": notification_view,
        "notification_duplicates": max(0, len(notifications) - 1),
    }
    actionable = executable and not blocked_by and len(notifications) <= 1
    return {
        "approval": ApprovalResponse.model_validate(approval).model_dump(mode="python"),
        "task": task_view,
        "review_digest": canonical_digest(review_document),
        "current": current,
        "executable": executable,
        "actionable": actionable,
        "blocked_by": blocked_by,
        "changed_fields": changed_fields,
        "prerequisites": prerequisites,
        "mission": mission_view,
        "authority_policy": policy_view,
        "notification": notification_view,
        "notification_duplicates": max(0, len(notifications) - 1),
        "events": [ApprovalEventResponse.model_validate(item) for item in events],
        "claim_boundary": (
            "The review digest binds the displayed task, scope, prerequisites, mission, "
            "authority policy and notification generation. It authorizes only one bounded "
            "task lease and grants no broader execution or capital authority."
        ),
    }


def approval_center(db: Session) -> dict:
    pending = list(
        db.scalars(
            select(TaskApproval)
            .where(TaskApproval.status == "pending")
            .order_by(TaskApproval.created_at.desc())
        ).all()
    )
    recent_decisions = list(
        db.scalars(
            select(TaskApproval)
            .where(TaskApproval.status != "pending")
            .order_by(TaskApproval.updated_at.desc())
            .limit(25)
        ).all()
    )
    approvals = [*pending, *recent_decisions]
    items = [approval_center_item(db, item) for item in approvals]
    status_counts = dict(
        db.execute(
            select(TaskApproval.status, func.count(TaskApproval.id)).group_by(
                TaskApproval.status
            )
        ).all()
    )
    return {
        "generated_at": datetime.now(UTC),
        "counts": {
            "pending": status_counts.get("pending", 0),
            "actionable": sum(item["actionable"] for item in items),
            "blocked": sum(
                item["approval"]["status"] == "pending" and not item["actionable"]
                for item in items
            ),
            "decided": sum(
                count for status, count in status_counts.items() if status != "pending"
            ),
        },
        "items": items,
    }
