from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.symbolic_search import SymbolicSearchCandidate, SymbolicSearchRun
from app.schemas.symbolic_search import (
    SymbolicCandidateCreate,
    SymbolicCandidateResponse,
    SymbolicSearchCreate,
    SymbolicSearchQuarantine,
    SymbolicSearchResponse,
)
from app.services.symbolic_search import (
    SymbolicSearchConflict,
    quarantine_run,
    register_symbolic_search,
    validate_candidate,
)

router = APIRouter(
    prefix="/v1/research/symbolic-searches",
    tags=["research-symbolic-search"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=SymbolicSearchResponse, status_code=201)
def create_run(payload: SymbolicSearchCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = register_symbolic_search(db, payload)
        db.commit()
        db.refresh(record)
        return SymbolicSearchResponse.model_validate(record)
    except SymbolicSearchConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[SymbolicSearchResponse])
def list_runs(db: Annotated[Session, Depends(get_db)]):
    return [
        SymbolicSearchResponse.model_validate(item)
        for item in db.scalars(
            select(SymbolicSearchRun).order_by(SymbolicSearchRun.created_at.desc())
        ).all()
    ]


@router.get("/{run_id}", response_model=SymbolicSearchResponse)
def get_run(run_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(SymbolicSearchRun, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Symbolic-search run not found.")
    return SymbolicSearchResponse.model_validate(record)


@router.post(
    "/{run_id}/candidates", response_model=SymbolicCandidateResponse, status_code=201
)
def submit_candidate(
    run_id: UUID,
    payload: SymbolicCandidateCreate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        record = validate_candidate(db, run_id, payload)
        db.commit()
        db.refresh(record)
        return SymbolicCandidateResponse.model_validate(record)
    except SymbolicSearchConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{run_id}/candidates", response_model=list[SymbolicCandidateResponse])
def list_candidates(run_id: UUID, db: Annotated[Session, Depends(get_db)]):
    if db.get(SymbolicSearchRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Symbolic-search run not found.")
    return [
        SymbolicCandidateResponse.model_validate(item)
        for item in db.scalars(
            select(SymbolicSearchCandidate)
            .where(SymbolicSearchCandidate.run_id == run_id)
            .order_by(SymbolicSearchCandidate.created_at)
        ).all()
    ]


@router.post("/{run_id}/quarantine", response_model=SymbolicSearchResponse)
def quarantine(
    run_id: UUID,
    payload: SymbolicSearchQuarantine,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        record = quarantine_run(db, run_id, payload.actor, payload.reason)
        db.commit()
        db.refresh(record)
        return SymbolicSearchResponse.model_validate(record)
    except SymbolicSearchConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
