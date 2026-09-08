from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.intelligence_evaluation import (
    IntelligenceEvaluationRun,
    IntelligenceEvaluationSuite,
)
from app.schemas.intelligence_evaluation import (
    IntelligenceRunCreate,
    IntelligenceSuiteCreate,
)
from app.services.intelligence_evaluation import (
    IntelligenceEvaluationConflict,
    evaluate_run,
    readiness,
    register_suite,
)

router = APIRouter(
    prefix="/v1/research/intelligence-evaluation",
    tags=["research-intelligence-evaluation"],
    dependencies=[Depends(require_orchestrator)],
)


def _suite_response(record: IntelligenceEvaluationSuite) -> dict:
    return {
        "id": str(record.id),
        "suite_version": record.suite_version,
        "scope": record.scope,
        "corpus_digest": record.corpus_digest,
        "projection_digest": record.projection_digest,
        "item_manifest": record.item_manifest,
        "thresholds": record.thresholds,
        "record_digest": record.record_digest,
        "created_by": record.created_by,
        "created_at": record.created_at,
    }


def _run_response(record: IntelligenceEvaluationRun) -> dict:
    return {
        "id": str(record.id),
        "suite_id": str(record.suite_id),
        "status": record.status,
        "corpus_digest": record.corpus_digest,
        "projection_digest": record.projection_digest,
        "model_runtime_digest": record.model_runtime_digest,
        "evaluator_id": record.evaluator_id,
        "metrics": record.metrics,
        "domain_results": record.domain_results,
        "limitations": record.limitations,
        "response_digest": record.response_digest,
        "evaluation_digest": record.evaluation_digest,
        "created_at": record.created_at,
    }


@router.post("/suites", status_code=201)
def create_suite(
    payload: IntelligenceSuiteCreate, db: Annotated[Session, Depends(get_db)]
):
    try:
        record = register_suite(db, payload)
        db.commit()
        db.refresh(record)
        return _suite_response(record)
    except IntelligenceEvaluationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/suites")
def list_suites(db: Annotated[Session, Depends(get_db)]):
    return [
        _suite_response(item)
        for item in db.scalars(
            select(IntelligenceEvaluationSuite).order_by(
                IntelligenceEvaluationSuite.created_at.desc()
            )
        ).all()
    ]


@router.post("/runs", status_code=201)
def create_run(payload: IntelligenceRunCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        record = evaluate_run(db, payload)
        db.commit()
        db.refresh(record)
        return _run_response(record)
    except IntelligenceEvaluationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(db: Annotated[Session, Depends(get_db)]):
    return [
        _run_response(item)
        for item in db.scalars(
            select(IntelligenceEvaluationRun).order_by(
                IntelligenceEvaluationRun.created_at.desc()
            )
        ).all()
    ]


@router.get("/readiness")
def get_readiness(db: Annotated[Session, Depends(get_db)]):
    return readiness(db)
