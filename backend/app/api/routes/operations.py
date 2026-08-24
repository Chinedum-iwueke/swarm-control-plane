from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.operation import Operation, OperationEvent
from app.schemas.operation import OperationEventResponse, OperationResponse
from app.services.operations import (
    mark_stalled_operations,
    operation_summary,
    reconcile_task_operations,
)

router = APIRouter(
    prefix="/v1/operations",
    tags=["operations"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("", response_model=list[OperationResponse])
def list_operations(
    db: Annotated[Session, Depends(get_db)],
    states: Annotated[list[str] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    reconcile_task_operations(db)
    mark_stalled_operations(db)
    statement = select(Operation).order_by(Operation.updated_at.desc()).limit(limit)
    if states:
        statement = statement.where(Operation.state.in_(states))
    return list(db.scalars(statement).all())


@router.get("/summary")
def read_operation_summary(db: Annotated[Session, Depends(get_db)]):
    return operation_summary(db)


@router.get("/{operation_id}/events", response_model=list[OperationEventResponse])
def operation_events(operation_id: UUID, db: Annotated[Session, Depends(get_db)]):
    if db.get(Operation, operation_id) is None:
        raise HTTPException(status_code=404, detail="Operation not found.")
    return list(
        db.scalars(
            select(OperationEvent)
            .where(OperationEvent.operation_id == operation_id)
            .order_by(OperationEvent.sequence)
        ).all()
    )
