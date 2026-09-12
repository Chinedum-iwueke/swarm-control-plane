from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.risk_budget_schema import RiskBudgetSchemaRegistry
from app.schemas.risk_budget_schema import (
    RiskBudgetSchemaCreate,
    RiskBudgetSchemaResponse,
)
from app.services.risk_budget_schema import (
    RiskBudgetSchemaConflict,
    register_risk_budget_schema,
)

router = APIRouter(
    prefix="/v1/research/risk-budget-schemas",
    tags=["research-risk-budget-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=RiskBudgetSchemaResponse, status_code=201)
def create_risk_budget_schema(payload: RiskBudgetSchemaCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_risk_budget_schema(db, payload)
        db.commit()
        db.refresh(record)
        return RiskBudgetSchemaResponse.model_validate(record)
    except RiskBudgetSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[RiskBudgetSchemaResponse])
def list_risk_budget_schemas(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(RiskBudgetSchemaRegistry).order_by(RiskBudgetSchemaRegistry.registered_at)
    ).all()
    return [RiskBudgetSchemaResponse.model_validate(item) for item in records]


@router.get("/{schema_id}", response_model=RiskBudgetSchemaResponse)
def get_risk_budget_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(RiskBudgetSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Risk-budget schema not found.")
    return RiskBudgetSchemaResponse.model_validate(record)
