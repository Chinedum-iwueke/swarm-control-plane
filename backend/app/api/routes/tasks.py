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
    TaskMutationResponse,
    TaskResponse,
    TaskResumeRequest,
)
from app.services.governance import rearm_task_approval
from app.services.missions import refresh_mission
from app.services.tasks import (
    append_task_event,
    build_task,
    persist_new_task,
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

    task = build_task(payload)

    try:
        persist_new_task(db, task)
        db.commit()
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task creation conflicted with existing data.",
        ) from exc

    db.refresh(task)

    return TaskResponse.model_validate(serialize_task(task))


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
        statement = statement.where(Task.status == task_status)

    if project is not None:
        statement = statement.where(Task.project == project)

    tasks = db.scalars(statement.order_by(Task.created_at.desc()).limit(limit)).all()

    return [TaskResponse.model_validate(serialize_task(task)) for task in tasks]


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


@router.post(
    "/{task_id}/rearm-approval",
    response_model=TaskMutationResponse,
)
def rearm_expired_task_approval(
    task_id: uuid.UUID,
    payload: TaskResumeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status not in {"pending_approval", "queued"} or not task.approval_required:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an approval-gated task pending approval or stranded queued "
                "work can be rearmed."
            ),
        )
    rearm_task_approval(db, task, payload.reason)
    event = append_task_event(
        db,
        task,
        "task_approval_rearmed",
        "Expired task approval returned to review.",
        payload={"requested_by": payload.requested_by, "reason": payload.reason},
    )
    db.commit()
    db.refresh(task)
    db.refresh(event)
    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )


@router.post(
    "/{task_id}/resume",
    response_model=TaskMutationResponse,
)
def resume_failed_task(
    task_id: uuid.UUID,
    payload: TaskResumeRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only a failed task can be resumed.",
        )

    previous_attempts = task.attempt_count
    task.max_attempts = max(task.max_attempts, previous_attempts + 1)
    task.completed_at = None
    task.result = {}
    rearm_task_approval(db, task, payload.reason)
    event = append_task_event(
        db,
        task,
        "task_resumed",
        "Failed task checkpoint resumed by operator.",
        payload={
            "requested_by": payload.requested_by,
            "reason": payload.reason,
            "previous_attempts": previous_attempts,
            "next_attempt": previous_attempts + 1,
        },
    )
    if task.mission_id is not None:
        refresh_mission(db, task.mission_id)
    db.commit()
    db.refresh(task)
    db.refresh(event)
    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
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
        task=TaskResponse.model_validate(serialize_task(task)),
        events=[TaskEventResponse.model_validate(event) for event in events],
    )
