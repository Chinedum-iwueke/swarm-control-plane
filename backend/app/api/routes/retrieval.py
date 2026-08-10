from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.ingestion import ScientificIngestionPipeline
from app.schemas.ingestion import CoordinateReplayResponse
from app.schemas.retrieval import (
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    ProjectionBuildResponse,
    ProjectionStatusResponse,
)
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.object_store import FilesystemEvidenceObjectStore
from app.services.retrieval import (
    build_projections,
    hybrid_search,
    projection_status,
)
from app.services.scientific_ingestion import replay_coordinate

router = APIRouter(
    prefix="/v1/research/retrieval",
    tags=["canonical-retrieval"],
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


@router.post("/projections/rebuild", response_model=ProjectionBuildResponse)
def rebuild_retrieval_projections(db: Annotated[Session, Depends(get_db)]):
    return build_projections(db)


@router.get("/projections/status", response_model=ProjectionStatusResponse)
def read_retrieval_projection_status(db: Annotated[Session, Depends(get_db)]):
    state, current, stale = projection_status(db)
    return ProjectionStatusResponse(
        projection_name=state.projection_name,
        projection_version=state.projection_version,
        corpus_digest=state.corpus_digest,
        current_corpus_digest=current,
        object_count=state.object_count,
        built_at=state.built_at,
        stale=stale,
    )


@router.post("/query", response_model=HybridRetrievalResponse)
def query_canonical_evidence(
    payload: HybridRetrievalRequest,
    db: Annotated[Session, Depends(get_db)],
):
    return hybrid_search(db, payload, ORCHESTRATOR_ACCESS)


@router.get(
    "/objects/{object_id}/replay", response_model=CoordinateReplayResponse
)
def replay_retrieval_citation(
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
