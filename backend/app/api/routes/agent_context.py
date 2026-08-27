from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_agent, require_orchestrator
from app.db.session import get_db
from app.models import Agent
from app.models.agent_context import AgentContextManifest, AgentWorkingMemoryReceipt
from app.schemas.agent_context import (
    AgentContextCreate,
    AgentContextResponse,
    ContextReplayRequest,
    WorkingMemoryCreate,
    WorkingMemoryResponse,
)
from app.services.agent_context import (
    active_context,
    create_context,
    record_working_memory,
    serialize_context,
)
from app.services.tasks import lock_task, verify_task_lease

router = APIRouter(
    prefix="/v1/agent-context",
    tags=["agent-context"],
    dependencies=[Depends(require_orchestrator)],
)
agent_router = APIRouter(prefix="/v1/agent/tasks", tags=["agent-context-runtime"])


@router.post("/manifests", response_model=AgentContextResponse, status_code=201)
def create(payload: AgentContextCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        return serialize_context(create_context(db, payload))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "A context manifest already exists for this task attempt."
        ) from exc


@router.get("/manifests/{manifest_id}", response_model=AgentContextResponse)
def read(manifest_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(AgentContextManifest, manifest_id)
    if record is None:
        raise HTTPException(404, "Context manifest not found.")
    return serialize_context(record)


@router.get("/tasks/{task_id}/manifests", response_model=list[AgentContextResponse])
def task_manifests(task_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return [
        serialize_context(item)
        for item in db.scalars(
            select(AgentContextManifest)
            .where(AgentContextManifest.task_id == task_id)
            .order_by(AgentContextManifest.attempt_number)
        )
    ]


@agent_router.post("/{task_id}/context", response_model=AgentContextResponse)
def replay(
    task_id: UUID,
    payload: ContextReplayRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    task = lock_task(db, task_id)
    verify_task_lease(
        task, agent, payload.lease_token, allowed_statuses={"leased", "running"}
    )
    return serialize_context(active_context(db, task, agent))


@agent_router.post(
    "/{task_id}/working-memory", response_model=WorkingMemoryResponse, status_code=201
)
def remember(
    task_id: UUID,
    payload: WorkingMemoryCreate,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
):
    task = lock_task(db, task_id)
    verify_task_lease(
        task, agent, payload.lease_token, allowed_statuses={"leased", "running"}
    )
    context = active_context(db, task, agent)
    try:
        return record_working_memory(db, context, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Working-memory sequence already exists.") from exc


@router.get(
    "/tasks/{task_id}/working-memory", response_model=list[WorkingMemoryResponse]
)
def memory(task_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(AgentWorkingMemoryReceipt)
            .where(AgentWorkingMemoryReceipt.task_id == task_id)
            .order_by(AgentWorkingMemoryReceipt.sequence)
        )
    )
