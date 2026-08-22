from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.ingestion import _pipeline, _store
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.ingestion import ScientificIngestionJob, ScientificIngestionRecovery
from app.schemas.ingestion import (
    BlockedArtifactRegisterResponse,
    IngestionRecoveryBatchResponse,
    IngestionRecoveryCreate,
    IngestionRecoveryResolutionResponse,
    IngestionRecoveryResponse,
)
from app.services.blocked_artifact_register import blocked_artifact_register
from app.services.ingestion_recovery import process_next_recovery, queue_recoveries
from app.services.scientific_ingestion import ingestion_response

router = APIRouter(
    prefix="/v1/research/ingestion/recoveries",
    tags=["scientific-ingestion-recovery"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/blocked-artifacts", response_model=BlockedArtifactRegisterResponse)
def list_blocked_artifacts(db: Annotated[Session, Depends(get_db)]):
    return blocked_artifact_register(db)


@router.get(
    "/by-original-job/{original_job_id}",
    response_model=IngestionRecoveryResolutionResponse,
)
def resolve_recovered_ingestion(
    original_job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    recovery = db.scalar(
        select(ScientificIngestionRecovery).where(
            ScientificIngestionRecovery.original_job_id == original_job_id,
            ScientificIngestionRecovery.status == "recovered",
        )
    )
    if recovery is None or recovery.sanitized_job_id is None:
        raise HTTPException(status_code=404, detail="Recovered ingestion not found.")
    sanitized = db.get(ScientificIngestionJob, recovery.sanitized_job_id)
    if sanitized is None or sanitized.status != "published":
        raise HTTPException(status_code=409, detail="Recovered ingestion is not published.")
    return IngestionRecoveryResolutionResponse(
        recovery=IngestionRecoveryResponse.model_validate(recovery, from_attributes=True),
        sanitized_job=ingestion_response(sanitized),
    )


@router.post("", response_model=IngestionRecoveryBatchResponse, status_code=202)
def create_recovery_batch(
    payload: IngestionRecoveryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    queued, existing, ids = queue_recoveries(db, payload)
    return IngestionRecoveryBatchResponse(
        queued=queued, existing=existing, recovery_ids=ids
    )


@router.post("/process-next", response_model=IngestionRecoveryResponse | None)
def process_next(db: Annotated[Session, Depends(get_db)]):
    return process_next_recovery(db, _store(), _pipeline())
