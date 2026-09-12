from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.portfolio_capacity_schema import PortfolioCapacitySchemaRegistry
from app.schemas.portfolio_capacity_schema import (
    PortfolioCapacitySchemaCreate,
    PortfolioCapacitySchemaResponse,
)
from app.services.portfolio_capacity_schema import (
    PortfolioCapacitySchemaConflict,
    register_portfolio_capacity_schema,
)

router = APIRouter(
    prefix="/v1/research/portfolio-capacity-schemas",
    tags=["research-portfolio-capacity-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=PortfolioCapacitySchemaResponse, status_code=201)
def create_portfolio_capacity_schema(
    payload: PortfolioCapacitySchemaCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_portfolio_capacity_schema(db, payload)
        db.commit()
        db.refresh(record)
        return PortfolioCapacitySchemaResponse.model_validate(record)
    except PortfolioCapacitySchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[PortfolioCapacitySchemaResponse])
def list_portfolio_capacity_schemas(db: Annotated[Session, Depends(get_db)]):
    records = db.scalars(
        select(PortfolioCapacitySchemaRegistry).order_by(PortfolioCapacitySchemaRegistry.registered_at)
    ).all()
    return [PortfolioCapacitySchemaResponse.model_validate(item) for item in records]


@router.get("/{schema_id}", response_model=PortfolioCapacitySchemaResponse)
def get_portfolio_capacity_schema(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(PortfolioCapacitySchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Portfolio-capacity schema not found.")
    return PortfolioCapacitySchemaResponse.model_validate(record)
