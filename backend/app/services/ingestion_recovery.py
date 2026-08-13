from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pdf_sanitizer import PdfSanitizationError, sanitize_pdf
from app.ingestion.pipeline import ScientificIngestionPipeline
from app.models.ingestion import ScientificIngestionJob, ScientificIngestionRecovery
from app.schemas.ingestion import IngestionRecoveryCreate
from app.services.object_store import EvidenceObjectStore, ObjectReference
from app.services.scientific_ingestion import process_ingestion

RECOVERABLE_REASONS = {
    "active PDF content is forbidden",
    "PDF parser rejected the artifact",
}


def queue_recoveries(db: Session, payload: IngestionRecoveryCreate) -> tuple[int, int, list[UUID]]:
    existing_ids = set(
        db.scalars(select(ScientificIngestionRecovery.original_job_id)).all()
    )
    candidates = list(
        db.scalars(
            select(ScientificIngestionJob)
            .where(
                ScientificIngestionJob.project == payload.project,
                ScientificIngestionJob.media_type == "application/pdf",
                ScientificIngestionJob.status == "rejected",
            )
            .order_by(ScientificIngestionJob.created_at)
        ).all()
    )
    queued = 0
    existing = 0
    ids: list[UUID] = []
    for job in candidates:
        if _latest_reason(job) not in RECOVERABLE_REASONS:
            continue
        if job.id in existing_ids:
            recovery = db.scalar(
                select(ScientificIngestionRecovery).where(
                    ScientificIngestionRecovery.original_job_id == job.id
                )
            )
            if recovery is not None:
                ids.append(recovery.id)
                existing += 1
            continue
        recovery = ScientificIngestionRecovery(
            schema_version=payload.schema_version,
            original_job_id=job.id,
            sanitized_job_id=None,
            status="queued",
            requested_by=payload.requested_by,
            receipt={
                "original_digest": job.content_digest,
                "original_retained": True,
                "source_status": job.status,
                "recovery_reason": _latest_reason(job),
            },
            updated_at=datetime.now(UTC),
        )
        db.add(recovery)
        db.flush()
        ids.append(recovery.id)
        existing_ids.add(job.id)
        queued += 1
        if queued >= payload.limit:
            break
    db.commit()
    return queued, existing, ids


def process_next_recovery(
    db: Session,
    store: EvidenceObjectStore,
    pipeline: ScientificIngestionPipeline,
) -> ScientificIngestionRecovery | None:
    recovery = db.scalar(
        select(ScientificIngestionRecovery)
        .where(ScientificIngestionRecovery.status == "queued")
        .order_by(ScientificIngestionRecovery.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if recovery is None:
        return None
    recovery.status = "processing"
    recovery.updated_at = datetime.now(UTC)
    db.commit()
    recovery_id = recovery.id
    try:
        return _recover(db, recovery_id, store, pipeline)
    except Exception as exc:
        db.rollback()
        recovery = db.get(ScientificIngestionRecovery, recovery_id)
        if recovery is None:
            raise RuntimeError("recovery record vanished") from exc
        receipt = dict(recovery.receipt)
        receipt.update(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "failure_category": type(exc).__name__,
                "failure_detail": str(exc)[:300],
                "original_retained": True,
            }
        )
        recovery.status = (
            "rejected" if isinstance(exc, PdfSanitizationError) else "remediation_required"
        )
        recovery.receipt = receipt
        recovery.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(recovery)
        return recovery


def _recover(
    db: Session,
    recovery_id: UUID,
    store: EvidenceObjectStore,
    pipeline: ScientificIngestionPipeline,
) -> ScientificIngestionRecovery:
    recovery = db.get(ScientificIngestionRecovery, recovery_id)
    if recovery is None:
        raise RuntimeError("recovery record is unavailable")
    original = db.get(ScientificIngestionJob, recovery.original_job_id)
    if original is None or original.status != "rejected":
        raise PdfSanitizationError("original job is not a terminal rejected artifact")
    content = store.get(
        ObjectReference(
            uri=original.quarantine_uri,
            content_digest=original.content_digest,
            byte_size=0,
        )
    )
    result = sanitize_pdf(content)
    reference = store.put(result.content, expected_digest=result.sanitized_digest)
    sanitized = db.scalar(
        select(ScientificIngestionJob).where(
            ScientificIngestionJob.content_digest == result.sanitized_digest
        )
    )
    if sanitized is None:
        now = datetime.now(UTC)
        source = dict(original.source)
        source["title"] = f"{source['title']} [inert recovered edition]"[:500]
        source["origin"] = f"{source['origin']}#hermes-inert-recovery-v1"[:2000]
        source["edition_label"] = f"sanitized-{result.sanitized_digest[:12]}"
        sanitized = ScientificIngestionJob(
            schema_version="scientific-ingestion-v1.0.0",
            project=original.project,
            filename=f"{Path(original.filename).stem[:160]}-sanitized.pdf",
            media_type="application/pdf",
            content_digest=result.sanitized_digest,
            quarantine_uri=reference.uri,
            access_class=original.access_class,
            source=source,
            requested_by=recovery.requested_by,
            status="quarantined",
            stage_report={
                "stages": [
                    {
                        "stage": "quarantine",
                        "status": "passed",
                        "at": now.isoformat(),
                        "artifact_digest": result.sanitized_digest,
                        "byte_size": len(result.content),
                        "recovered_from_job_id": str(original.id),
                        "recovered_from_digest": original.content_digest,
                    }
                ]
            },
            published_object_ids=[],
            updated_at=now,
        )
        db.add(sanitized)
        db.commit()
        db.refresh(sanitized)
    sanitized = process_ingestion(db, sanitized.id, store, pipeline)
    receipt = {
        "schema_version": "pdf-sanitization-receipt-v1.0.0",
        "original_job_id": str(original.id),
        "original_digest": result.original_digest,
        "original_retained": True,
        "sanitized_job_id": str(sanitized.id),
        "sanitized_digest": result.sanitized_digest,
        "sanitizer": "hermes-inert-pdf-v1",
        "page_count": result.page_count,
        "text_digest": result.text_digest,
        "text_equivalent": True,
        "visual_sample_digest": result.visual_sample_digest,
        "visual_sample_pages": result.visual_sample_pages,
        "visual_samples_equivalent": True,
        "removed": result.removed,
        "normal_pipeline_status": sanitized.status,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    recovery = db.get(ScientificIngestionRecovery, recovery_id)
    if recovery is None:
        raise RuntimeError("recovery record is unavailable after publication")
    recovery.sanitized_job_id = sanitized.id
    recovery.status = "recovered" if sanitized.status == "published" else "remediation_required"
    recovery.receipt = receipt
    recovery.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(recovery)
    return recovery


def requeue_stale_recoveries(db: Session, *, stale_after_seconds: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    records = list(
        db.scalars(
            select(ScientificIngestionRecovery).where(
                ScientificIngestionRecovery.status == "processing",
                ScientificIngestionRecovery.updated_at <= cutoff,
            )
        ).all()
    )
    for record in records:
        receipt = dict(record.receipt)
        receipt["stale_claim_requeued_at"] = datetime.now(UTC).isoformat()
        record.receipt = receipt
        record.status = "queued"
        record.updated_at = datetime.now(UTC)
    db.commit()
    return len(records)


def _latest_reason(job: ScientificIngestionJob) -> str | None:
    stages = job.stage_report.get("stages", [])
    return stages[-1].get("reason") if stages else None
