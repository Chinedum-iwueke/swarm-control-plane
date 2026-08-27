from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.selection_audit import SelectionBiasAudit
from app.schemas.selection_audit import (
    SelectionBiasAuditCreate,
    SelectionBiasAuditResponse,
)
from app.services.selection_audit import (
    SelectionAuditConflict,
    register_selection_audit,
)

router = APIRouter(
    prefix="/v1/research/selection-audits",
    tags=["research-selection-audit"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=SelectionBiasAuditResponse, status_code=201)
def create_audit(
    payload: SelectionBiasAuditCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_selection_audit(db, payload)
        db.commit()
        db.refresh(record)
        return SelectionBiasAuditResponse.model_validate(record)
    except SelectionAuditConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[SelectionBiasAuditResponse])
def list_audits(
    db: Annotated[Session, Depends(get_db)],
    mechanism_evaluation_id: UUID | None = None,
):
    statement = select(SelectionBiasAudit)
    if mechanism_evaluation_id:
        statement = statement.where(
            SelectionBiasAudit.mechanism_evaluation_id == mechanism_evaluation_id
        )
    return [
        SelectionBiasAuditResponse.model_validate(item)
        for item in db.scalars(
            statement.order_by(SelectionBiasAudit.audited_at.desc())
        ).all()
    ]
