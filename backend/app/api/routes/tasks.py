from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import Task, TaskEvent
from app.schemas import (
    ExpiredLeaseReapResponse,
    TaskCreate,
    TaskDetailResponse,
    TaskEventResponse,
    TaskResponse,
)
from app.services.governance import create_approval, task_plan_digest
from app.services.tasks import (
    append_task_event,
    reap_expired_leases,
    serialize_task,
)

router = APIRouter(
    prefix="/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreate,
    db: Annotated[Session, Depends(get_db)],
) -> TaskResponse:
    if payload.parent_task_id is not None:
        parent = db.get(Task, payload.parent_task_id)

        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent task not found.",
            )

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
    task = Task(
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

    db.add(task)

    try:
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
                "created_by": payload.created_by,
                "priority": payload.priority,
                "risk_level": payload.risk_level,
            },
        )

        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task creation conflicted with existing data.",
        ) from exc

    db.refresh(task)

    return TaskResponse.model_validate(
        serialize_task(task)
    )


@router.get(
    "",
    response_model=list[TaskResponse],
)
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    task_status: Annotated[str | None, Query(alias="status")] = None,
    project: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[TaskResponse]:
    statement = select(Task)

    if task_status is not None:
        statement = statement.where(
            Task.status == task_status
        )

    if project is not None:
        statement = statement.where(
            Task.project == project
        )

    tasks = db.scalars(
        statement
        .order_by(
            Task.created_at.desc()
        )
        .limit(limit)
    ).all()

    return [
        TaskResponse.model_validate(
            serialize_task(task)
        )
        for task in tasks
    ]


@router.post(
    "/reap-expired-leases",
    response_model=ExpiredLeaseReapResponse,
)
def reap_task_leases(
    db: Annotated[Session, Depends(get_db)],
) -> ExpiredLeaseReapResponse:
    inspected, requeued, failed = reap_expired_leases(db)
    db.commit()

    return ExpiredLeaseReapResponse(
        inspected=inspected,
        requeued=requeued,
        failed=failed,
    )


@router.get(
    "/{task_id}",
    response_model=TaskDetailResponse,
)
def get_task(
    task_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> TaskDetailResponse:
    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    events = db.scalars(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.id.asc())
    ).all()

    return TaskDetailResponse(
        task=TaskResponse.model_validate(
            serialize_task(task)
        ),
        events=[
            TaskEventResponse.model_validate(event)
            for event in events
        ],
    )
