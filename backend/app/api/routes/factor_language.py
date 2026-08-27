from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.factor_language import FactorExperimentProgram
from app.schemas.factor_language import FactorProgramCreate, FactorProgramResponse
from app.services.factor_language import FactorLanguageConflict, register_factor_program

router = APIRouter(
    prefix="/v1/research/factor-programs",
    tags=["research-factor-language"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=FactorProgramResponse, status_code=201)
def create_program(
    payload: FactorProgramCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_factor_program(db, payload)
        db.commit()
        db.refresh(record)
        return FactorProgramResponse.model_validate(record)
    except FactorLanguageConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[FactorProgramResponse])
def list_programs(
    db: Annotated[Session, Depends(get_db)], hypothesis_id: UUID | None = None
):
    statement = select(FactorExperimentProgram)
    if hypothesis_id:
        statement = statement.where(
            FactorExperimentProgram.hypothesis_id == hypothesis_id
        )
    return [
        FactorProgramResponse.model_validate(item)
        for item in db.scalars(
            statement.order_by(FactorExperimentProgram.registered_at.desc())
        ).all()
    ]


@router.get("/{program_id}", response_model=FactorProgramResponse)
def get_program(program_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(FactorExperimentProgram, program_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Factor program not found.")
    return FactorProgramResponse.model_validate(record)
