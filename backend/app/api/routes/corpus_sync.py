from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.corpus_sync import CorpusSyncRun
from app.models.ingestion import ScientificIngestionJob
from app.models.research import ResearchDocument
from app.schemas.corpus_sync import CorpusSyncRunCreate, CorpusSyncRunResponse
from app.services.corpus_sync import corpus_sync_response, reconcile_corpus

router = APIRouter(
    prefix="/v1/research/corpus-sync",
    tags=["corpus-sync"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/runs", response_model=CorpusSyncRunResponse, status_code=201)
def create_sync_run(payload: CorpusSyncRunCreate, db: Annotated[Session, Depends(get_db)]):
    return corpus_sync_response(db, reconcile_corpus(db, payload))


@router.get("/runs/{run_id}", response_model=CorpusSyncRunResponse)
def get_sync_run(run_id: UUID, db: Annotated[Session, Depends(get_db)]):
    run = db.get(CorpusSyncRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Corpus synchronization run not found.")
    return corpus_sync_response(db, run)


@router.post("/legacy-hermes/inventory", response_model=CorpusSyncRunResponse)
def inventory_legacy_hermes(db: Annotated[Session, Depends(get_db)]):
    documents = list(
        db.scalars(select(ResearchDocument).order_by(ResearchDocument.document_key)).all()
    )
    jobs = {
        job.content_digest: job
        for job in db.scalars(
            select(ScientificIngestionJob).where(
                ScientificIngestionJob.content_digest.in_(
                    [document.content_digest for document in documents]
                )
            )
        ).all()
    }
    items = []
    for document in documents:
        job = jobs.get(document.content_digest)
        canonical = job is not None and job.status == "published"
        items.append(
            {
                "source_locator": f"document/{document.document_key}",
                "content_digest": document.content_digest,
                "classification": {
                    "document_type": document.document_type,
                    "evidence_type": document.evidence_type,
                    "legacy_source_uri": document.source_uri,
                },
                "access_class": "internal",
                "disposition": "canonical" if canonical else "excluded",
                "ingestion_job_id": str(job.id) if canonical else None,
                "detail": None if canonical else (
                    "Original source artifact is unavailable in canonical quarantine; "
                    "refresh its bounded source lane rather than promoting derived chunks."
                ),
            }
        )
    run = reconcile_corpus(
        db,
        CorpusSyncRunCreate.model_validate(
            {
                "schema_version": "corpus-sync-v1.0.0",
                "project": "systematic-research",
                "source_kind": "legacy_hermes",
                "source_root": "legacy-research-documents",
                "requested_by": "corpus-curator",
                "items": items,
            }
        ),
    )
    return corpus_sync_response(db, run)
