from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.ingestion import ScientificIngestionPipeline
from app.models.ingestion import ScientificIngestionJob
from app.schemas.ingestion import (
    CoordinateReplayResponse,
    ScientificIngestionCreate,
    ScientificIngestionResponse,
)
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.object_store import FilesystemEvidenceObjectStore
from app.services.scientific_ingestion import (
    ingestion_response,
    process_ingestion,
    quarantine_ingestion,
    replay_coordinate,
)

router = APIRouter(
    prefix="/v1/research/ingestion",
    tags=["scientific-ingestion"],
    dependencies=[Depends(require_orchestrator)],
)


@lru_cache
def _store() -> FilesystemEvidenceObjectStore:
    return FilesystemEvidenceObjectStore(get_settings().evidence_object_root)


@lru_cache
def _pipeline() -> ScientificIngestionPipeline:
    settings = get_settings()
    return ScientificIngestionPipeline(
        max_bytes=settings.scientific_ingestion_max_bytes
    )


@router.post("/jobs", response_model=ScientificIngestionResponse, status_code=202)
def create_ingestion_job(
    payload: ScientificIngestionCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return ingestion_response(
        quarantine_ingestion(
            db,
            payload,
            _store(),
            max_bytes=get_settings().scientific_ingestion_max_bytes,
        )
    )


@router.get("/jobs/{job_id}", response_model=ScientificIngestionResponse)
def get_ingestion_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    job = db.get(ScientificIngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scientific ingestion job not found.")
    return ingestion_response(job)


@router.post(
    "/jobs/{job_id}/process", response_model=ScientificIngestionResponse, status_code=200
)
def process_ingestion_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    return ingestion_response(process_ingestion(db, job_id, _store(), _pipeline()))


@router.get(
    "/objects/{object_id}/replay", response_model=CoordinateReplayResponse
)
def replay_scientific_coordinate(
    object_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    return replay_coordinate(
        db,
        object_id,
        ORCHESTRATOR_ACCESS,
        _store(),
        _pipeline(),
    )
