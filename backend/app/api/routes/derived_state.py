from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.derived_state import (
    DerivedStatePhaseReceipt,
    DerivedStateReconciliation,
)
from app.schemas.derived_state import (
    DerivedStatePhaseReceiptResponse,
    DerivedStateRunResponse,
    DerivedStateSchedule,
    DerivedStateStatus,
)
from app.services.derived_state import (
    derived_state_status,
    execute_reconciliation,
    schedule_reconciliation,
)

router = APIRouter(
    prefix="/v1/research/derived-state",
    tags=["research-derived-state"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/reconciliations",
    response_model=DerivedStateRunResponse | None,
    status_code=202,
)
def create_reconciliation(
    payload: DerivedStateSchedule,
    db: Annotated[Session, Depends(get_db)],
):
    return schedule_reconciliation(
        db, requested_by=payload.requested_by, force_full=payload.force_full
    )


@router.post(
    "/reconciliations/{run_id}/execute",
    response_model=DerivedStateRunResponse,
)
def execute_run(run_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return execute_reconciliation(db, run_id)


@router.get("/reconciliations", response_model=list[DerivedStateRunResponse])
def list_reconciliations(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return list(
        db.scalars(
            select(DerivedStateReconciliation)
            .order_by(DerivedStateReconciliation.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.get(
    "/reconciliations/{run_id}/receipts",
    response_model=list[DerivedStatePhaseReceiptResponse],
)
def list_phase_receipts(run_id: UUID, db: Annotated[Session, Depends(get_db)]):
    if db.get(DerivedStateReconciliation, run_id) is None:
        raise HTTPException(status_code=404, detail="Derived-state run not found.")
    return list(
        db.scalars(
            select(DerivedStatePhaseReceipt)
            .where(DerivedStatePhaseReceipt.reconciliation_id == run_id)
            .order_by(DerivedStatePhaseReceipt.started_at)
        ).all()
    )


@router.get("/status", response_model=DerivedStateStatus)
def read_status(db: Annotated[Session, Depends(get_db)]):
    return derived_state_status(db)
