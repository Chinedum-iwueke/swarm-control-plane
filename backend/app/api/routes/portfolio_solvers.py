from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.portfolio_solver import PortfolioSolverRegistry
from app.schemas.portfolio_solver import PortfolioSolverCreate, PortfolioSolverResponse
from app.services.portfolio_solver import PortfolioSolverConflict, register_solver

router = APIRouter(
    prefix="/v1/research/portfolio-solvers",
    tags=["research-portfolio-solvers"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=PortfolioSolverResponse, status_code=201)
def create_solver(payload: PortfolioSolverCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_solver(db, payload)
        db.commit()
        db.refresh(record)
        return PortfolioSolverResponse.model_validate(record)
    except PortfolioSolverConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[PortfolioSolverResponse])
def list_solvers(db: Annotated[Session, Depends(get_db)]):
    return [
        PortfolioSolverResponse.model_validate(item)
        for item in db.scalars(select(PortfolioSolverRegistry).order_by(PortfolioSolverRegistry.registered_at)).all()
    ]


@router.get("/{solver_id}", response_model=PortfolioSolverResponse)
def get_solver(solver_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(PortfolioSolverRegistry, solver_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Portfolio solver not found.")
    return PortfolioSolverResponse.model_validate(record)
