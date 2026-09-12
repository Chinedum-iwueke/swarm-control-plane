from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.candidate_admission_schema import CandidateAdmissionSchemaRegistry
from app.schemas.candidate_admission_schema import (
    CandidateAdmissionSchemaCreate,
    CandidateAdmissionSchemaResponse,
)
from app.services.candidate_admission_schema import (
    CandidateAdmissionSchemaConflict,
    register_candidate_admission_schema,
)

router = APIRouter(
    prefix="/v1/research/candidate-admission-schemas",
    tags=["research-candidate-admission-schemas"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=CandidateAdmissionSchemaResponse, status_code=201)
def create(
    payload: CandidateAdmissionSchemaCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_candidate_admission_schema(db, payload)
        db.commit()
        db.refresh(record)
        return record
    except CandidateAdmissionSchemaConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[CandidateAdmissionSchemaResponse])
def list_schemas(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(
            select(CandidateAdmissionSchemaRegistry).order_by(
                CandidateAdmissionSchemaRegistry.registered_at
            )
        ).all()
    )


@router.get("/{schema_id}", response_model=CandidateAdmissionSchemaResponse)
def get(schema_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(CandidateAdmissionSchemaRegistry, schema_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Candidate-admission schema not found."
        )
    return record
