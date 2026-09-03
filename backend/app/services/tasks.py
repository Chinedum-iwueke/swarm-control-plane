from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.security import (
    create_task_lease_token,
    digest_task_lease_token,
    extract_task_lease_token_prefix,
)
from app.models import (
    Agent,
    EngineeringMission,
    Task,
    TaskApproval,
    TaskDependency,
    TaskEvent,
    TaskGraph,
    TaskGraphNode,
)
from app.schemas.agent_governance import EffectiveAuthorityRequest
from app.schemas.task import TaskCreate
from app.services.agent_governance import resolve as resolve_agent_authority
from app.services.governance import (
    consume_task_approval,
    create_approval,
    expire_approvals,
    rearm_task_approval,
    task_plan_digest,
)

ACTIVE_LEASE_STATUSES = {"leased", "running"}


def resolve_task_authority(
    db: Session, task: Task, agent: Agent, now: datetime
) -> list[dict]:
    return [
        resolve_agent_authority(
            db,
            agent.id,
            EffectiveAuthorityRequest(
                capability=capability,
                machine=agent.machine,
                task_type=task.task_type,
                repository=task.project,
                risk_level=task.risk_level,
            ),
            now,
        )
        for capability in task.required_capabilities
    ]


def build_task(payload: TaskCreate) -> Task:
    plan_document = {
        "project": payload.project,
        "task_type": payload.task_type,
        "objective": payload.objective,
        "risk_level": payload.risk_level,
        "input_contract": payload.input_contract,
        "expected_outputs": payload.expected_outputs,
        "acceptance_criteria": payload.acceptance_criteria,
        "required_capabilities": payload.required_capabilities,
        "allowed_machines": payload.allowed_machines,
    }
    approval_required = payload.approval_required or payload.risk_level >= 2
    return Task(
        task_number=payload.task_number,
        project=payload.project,
        task_type=payload.task_type,
        title=payload.title,
        objective=payload.objective,
        status="pending_approval" if approval_required else "queued",
        priority=payload.priority,
        risk_level=payload.risk_level,
        parent_task_id=payload.parent_task_id,
        created_by=payload.created_by,
        input_contract=payload.input_contract,
        expected_outputs=payload.expected_outputs,
        acceptance_criteria=payload.acceptance_criteria,
        approval_policy=payload.approval_policy,
        approval_required=approval_required,
        plan_digest=task_plan_digest(plan_document),
        required_capabilities=payload.required_capabilities,
        allowed_machines=payload.allowed_machines,
        max_attempts=payload.max_attempts,
        attempt_count=0,
        result={},
        failure={},
    )


def persist_new_task(db: Session, task: Task) -> None:
    db.add(task)
    db.flush()
    if task.approval_required:
        create_approval(db, task)
    append_task_event(
        db,
        task,
        "task_created",
        (
            "Task created pending approval."
            if task.approval_required
            else "Task created and queued."
        ),
        payload={
            "created_by": task.created_by,
            "priority": task.priority,
            "risk_level": task.risk_level,
        },
    )


def utc_now() -> datetime:
    return datetime.now(UTC)


def serialize_task(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "task_number": task.task_number,
        "project": task.project,
        "task_type": task.task_type,
        "title": task.title,
        "objective": task.objective,
        "status": task.status,
        "priority": task.priority,
        "risk_level": task.risk_level,
        "assigned_agent_id": task.assigned_agent_id,
        "parent_task_id": task.parent_task_id,
        "conversation_id": task.conversation_id,
        "conversation_revision": task.conversation_revision,
        "mission_id": task.mission_id,
        "milestone_step_id": task.milestone_step_id,
        "task_graph_node_id": task.task_graph_node_id,
        "created_by": task.created_by,
        "input_contract": task.input_contract,
        "expected_outputs": task.expected_outputs,
        "acceptance_criteria": task.acceptance_criteria,
        "approval_policy": task.approval_policy,
        "approval_required": task.approval_required,
        "plan_digest": task.plan_digest,
        "required_capabilities": task.required_capabilities,
        "allowed_machines": task.allowed_machines,
        "max_attempts": task.max_attempts,
        "attempt_count": task.attempt_count,
        "leased_at": task.leased_at,
        "lease_expires_at": task.lease_expires_at,
        "last_execution_heartbeat_at": task.last_execution_heartbeat_at,
        "result": task.result,
        "failure": task.failure,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "cancel_requested_at": task.cancel_requested_at,
        "cancel_reason": task.cancel_reason,
    }


def append_task_event(
    db: Session,
    task: Task,
    event_type: str,
    message: str,
    *,
    agent_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> TaskEvent:
    event = TaskEvent(
        task_id=task.id,
        agent_id=agent_id,
        event_type=event_type,
        attempt_number=task.attempt_count,
        message=message,
        payload=payload or {},
    )

    db.add(event)
    db.flush()

    return event


def clear_lease(task: Task) -> None:
    task.assigned_agent_id = None
    task.leased_at = None
    task.lease_expires_at = None
    task.lease_token_prefix = None
    task.lease_token_digest = None
    task.last_execution_heartbeat_at = None


def verify_task_lease(
    task: Task,
    agent: Agent,
    supplied_token: str,
    *,
    allowed_statuses: set[str],
    now: datetime | None = None,
) -> datetime:
    current_time = now or utc_now()

    if task.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Task is in state '{task.status}', but this operation "
                f"requires one of: {sorted(allowed_statuses)}."
            ),
        )

    if task.assigned_agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This task lease belongs to another agent.",
        )

    if task.lease_expires_at is None or task.lease_expires_at <= current_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task lease has expired.",
        )

    supplied_prefix = extract_task_lease_token_prefix(supplied_token)

    if (
        supplied_prefix is None
        or task.lease_token_prefix is None
        or supplied_prefix != task.lease_token_prefix
        or task.lease_token_digest is None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid task lease token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied_digest = digest_task_lease_token(supplied_token)

    if not hmac.compare_digest(
        supplied_digest,
        task.lease_token_digest,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid task lease token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_time


def lease_next_task(
    db: Session,
    agent: Agent,
    lease_seconds: int,
) -> tuple[Task | None, str | None, TaskEvent | None]:
    now = utc_now()
    expire_approvals(db, now)
    predecessor = aliased(Task)
    blocked_dependency = (
        select(TaskDependency.id)
        .join(predecessor, predecessor.id == TaskDependency.depends_on_task_id)
        .where(
            TaskDependency.task_id == Task.id,
            predecessor.status != "succeeded",
        )
    )
    valid_approval = or_(
        Task.approval_required.is_(False),
        exists(
            select(TaskApproval.id).where(
                TaskApproval.task_id == Task.id,
                TaskApproval.status == "approved",
                TaskApproval.plan_digest == Task.plan_digest,
                TaskApproval.expires_at.is_not(None),
                TaskApproval.expires_at > now,
            )
        ),
    )
    active_graph_tasks = aliased(Task)
    active_graph_nodes = aliased(TaskGraphNode)
    graph_parallelism_available = or_(
        Task.task_graph_node_id.is_(None),
        exists(
            select(TaskGraphNode.id)
            .join(TaskGraph, TaskGraph.id == TaskGraphNode.graph_id)
            .where(
                TaskGraphNode.id == Task.task_graph_node_id,
                TaskGraph.status == "active",
                select(func.count(active_graph_tasks.id))
                .join(active_graph_nodes, active_graph_tasks.task_graph_node_id == active_graph_nodes.id)
                .where(
                    active_graph_nodes.graph_id == TaskGraph.id,
                    active_graph_tasks.status.in_(ACTIVE_LEASE_STATUSES),
                )
                .scalar_subquery()
                < TaskGraph.max_parallelism,
            )
        ),
    )

    candidates = db.scalars(
        select(Task)
        .where(
            Task.status == "queued",
            Task.attempt_count < Task.max_attempts,
            Task.risk_level <= agent.risk_ceiling,
            Task.required_capabilities.contained_by(agent.capabilities),
            valid_approval,
            graph_parallelism_available,
            or_(
                Task.mission_id.is_(None),
                exists(
                    select(EngineeringMission.id).where(
                        EngineeringMission.id == Task.mission_id,
                        EngineeringMission.status == "active",
                        EngineeringMission.deadline_at > now,
                    )
                ),
            ),
            ~exists(blocked_dependency),
            or_(
                func.jsonb_array_length(Task.allowed_machines) == 0,
                Task.allowed_machines.contains([agent.machine]),
            ),
        )
        .order_by(
            Task.priority.desc(),
            Task.created_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(100)
    ).all()

    task = None
    for candidate in candidates:
        authority_snapshots = resolve_task_authority(db, candidate, agent, now)
        if authority_snapshots and all(
            item["allowed"] for item in authority_snapshots
        ):
            task = candidate
            break
        reasons = sorted(
            {
                reason
                for item in authority_snapshots
                for reason in item.get("reasons", [])
            }
        ) or ["authority-resolution-unavailable"]
        prior = db.scalar(
            select(TaskEvent)
            .where(
                TaskEvent.task_id == candidate.id,
                TaskEvent.event_type == "task_authority_denied",
            )
            .order_by(TaskEvent.id.desc())
            .limit(1)
        )
        if prior is None or prior.payload.get("reasons") != reasons:
            append_task_event(
                db,
                candidate,
                "task_authority_denied",
                "Task matched the worker but effective authority denied its lease.",
                agent_id=agent.id,
                payload={"reasons": reasons},
            )

    if task is None:
        return None, None, None

    consume_task_approval(db, task, now)

    generated = create_task_lease_token()

    task.status = "leased"
    task.assigned_agent_id = agent.id
    task.attempt_count += 1
    task.leased_at = now
    task.lease_expires_at = now + timedelta(seconds=lease_seconds)
    task.lease_token_prefix = generated.prefix
    task.lease_token_digest = generated.digest
    task.last_execution_heartbeat_at = now
    task.failure = {}

    event = append_task_event(
        db,
        task,
        "task_leased",
        "Task leased to agent.",
        agent_id=agent.id,
        payload={
            "lease_expires_at": (task.lease_expires_at.isoformat()),
            "lease_seconds": lease_seconds,
            "effective_authority": [
                {
                    "capability": capability,
                    "snapshot_digest": snapshot["snapshot_digest"],
                    "charter_digest": snapshot["charter_digest"],
                    "package_digest": snapshot["package_digest"],
                    "grant_digest": snapshot["grant_digest"],
                    "accountable_owner": snapshot["accountable_owner"],
                }
                for capability, snapshot in zip(
                    task.required_capabilities, authority_snapshots, strict=True
                )
            ],
        },
    )

    return task, generated.token, event


def lock_task(
    db: Session,
    task_id: uuid.UUID,
) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    return task


def reap_expired_leases(
    db: Session,
) -> tuple[int, int, int]:
    now = utc_now()

    expired_tasks = db.scalars(
        select(Task)
        .where(
            Task.status.in_(ACTIVE_LEASE_STATUSES),
            Task.lease_expires_at.is_not(None),
            Task.lease_expires_at <= now,
        )
        .order_by(Task.lease_expires_at.asc())
        .with_for_update(skip_locked=True)
    ).all()

    requeued = 0
    failed = 0

    for task in expired_tasks:
        previous_agent_id = task.assigned_agent_id
        previous_status = task.status
        expired_at = task.lease_expires_at

        append_task_event(
            db,
            task,
            "lease_expired",
            "Task lease expired.",
            agent_id=previous_agent_id,
            payload={
                "previous_status": previous_status,
                "lease_expires_at": (
                    expired_at.isoformat() if expired_at is not None else None
                ),
            },
        )

        if task.attempt_count >= task.max_attempts:
            task.status = "failed"
            task.failure = {
                "reason": "lease_expired",
                "message": ("Maximum attempts reached after lease expiry."),
            }
            task.completed_at = now

            append_task_event(
                db,
                task,
                "task_failed",
                "Task failed after exhausting lease attempts.",
                agent_id=previous_agent_id,
                payload=task.failure,
            )

            failed += 1
        else:
            rearm_task_approval(
                db, task, "A new approval is required after lease expiry."
            )

            append_task_event(
                db,
                task,
                "task_requeued",
                "Task returned for approval or requeued after lease expiry.",
                agent_id=previous_agent_id,
                payload={},
            )

            requeued += 1

        clear_lease(task)

    return len(expired_tasks), requeued, failed
