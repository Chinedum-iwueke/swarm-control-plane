from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import ScientificIngestionPipeline
from app.models.ingestion import ScientificIngestionJob
from app.services.object_store import EvidenceObjectStore
from app.services.scientific_ingestion import process_ingestion


def process_next_scientific_ingestion(
    db: Session,
    store: EvidenceObjectStore,
    pipeline: ScientificIngestionPipeline,
) -> ScientificIngestionJob | None:
    """Claim and process one job; callers own scheduling and bounded retries."""
    job = db.scalar(
        select(ScientificIngestionJob)
        .where(
            ScientificIngestionJob.status.in_(
                ("quarantined", "remediation_required")
            )
        )
        .order_by(ScientificIngestionJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    return process_ingestion(db, job.id, store, pipeline)
