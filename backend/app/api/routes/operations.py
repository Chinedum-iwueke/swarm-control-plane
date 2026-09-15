from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.operation import Operation, OperationEvent
from app.schemas.operation import (
    OperationEventResponse,
    OperationResponse,
    OperationWrite,
)
from app.services.operations import (
    mark_stalled_operations,
    operation_summary,
    reconcile_task_operations,
    upsert_operation,
)

router = APIRouter(
    prefix="/v1/operations",
    tags=["operations"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/lake-inventory/report", response_model=OperationResponse)
def report_lake_inventory(payload: OperationWrite, db: Annotated[Session, Depends(get_db)]):
    if (
        not payload.operation_key.startswith("lake-inventory:")
        or payload.kind != "full_lake_inventory"
        or payload.project != "bulletproof-bt"
        or payload.machine != "vm1-developer"
        or payload.owner_type != "system"
        or payload.owner_id != "founder-operator"
        or payload.cancellable
    ):
        raise HTTPException(422, "Report must bind the no-capital native lake inventory operation.")
    previous = db.scalar(select(Operation).where(Operation.operation_key == payload.operation_key))
    if previous is not None and previous.kind != "full_lake_inventory":
        raise HTTPException(409, "Operation key belongs to another workload.")
    record = upsert_operation(db, payload, actor="founder-operator")
    db.refresh(record)
    return record

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
