from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pdf_sanitizer import (
    PdfSanitizationError,
    recover_pdf_as_inert_text,
    recover_pdf_with_offline_ocr,
    sanitize_pdf,
)
from app.ingestion.pipeline import ScientificIngestionPipeline
from app.ingestion.recovery_controller import (
    RecoveryAdviser,
    RecoveryDiagnostic,
    RecoveryMethod,
    deterministic_terminal_classification,
    select_next_method,
)
from app.models.ingestion import ScientificIngestionJob, ScientificIngestionRecovery
from app.schemas.ingestion import IngestionRecoveryCreate
from app.services.object_store import EvidenceObjectStore, ObjectReference
from app.services.scientific_ingestion import process_ingestion

RECOVERABLE_REASONS = {
    "active PDF content is forbidden",
    "PDF parser rejected the artifact",
}


def queue_recoveries(
    db: Session, payload: IngestionRecoveryCreate
) -> tuple[int, int, list[UUID]]:
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
    adviser: RecoveryAdviser | None = None,
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
        return _recover(db, recovery_id, store, pipeline, adviser)
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
        attempts = list(receipt.get("attempts", []))
        if attempts:
            attempts[-1] = {
                **attempts[-1],
                "completed_at": datetime.now(UTC).isoformat(),
                "outcome": "failed",
                "failure_category": type(exc).__name__,
                "failure_detail": str(exc)[:300],
            }
            receipt["attempts"] = attempts
        attempted_methods = [item["method"] for item in attempts]
        remaining = [item for item in _METHODS if item not in attempted_methods]
        if isinstance(exc, PdfSanitizationError) and remaining:
            recovery.status = "queued"
            receipt["next_attempt_pending"] = True
        else:
            recovery.status = "rejected"
            receipt["terminal_classification"] = deterministic_terminal_classification(
                rejection_reason=str(exc), attempted_methods=attempted_methods
            )
            receipt["founder_action"] = _founder_action(
                receipt["terminal_classification"]
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
    adviser: RecoveryAdviser | None,
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
    receipt = dict(recovery.receipt)
    attempts = list(receipt.get("attempts", []))
    attempted_methods = [item["method"] for item in attempts]
    available_methods = [item for item in _METHODS if item not in attempted_methods]
    diagnostic = RecoveryDiagnostic(
        filename=original.filename,
        media_type=original.media_type,
        rejection_stage=_latest_stage(original) or "unknown",
        rejection_reason=_latest_reason(original) or "unknown rejection",
        attempted_methods=attempted_methods,
        available_methods=available_methods,
    )
    method, advice = select_next_method(diagnostic, adviser)
    if method is None:
        classification = deterministic_terminal_classification(
            rejection_reason=diagnostic.rejection_reason,
            attempted_methods=attempted_methods,
        )
        receipt["terminal_classification"] = classification
        receipt["founder_action"] = _founder_action(classification)
        recovery.status = "rejected"
        recovery.receipt = receipt
        recovery.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(recovery)
        return recovery
    attempt = {
        "number": len(attempts) + 1,
        "method": method,
        "started_at": datetime.now(UTC).isoformat(),
    }
    if advice is not None:
        attempt["codex_advice"] = {
            "action": advice.action,
            "terminal_classification": advice.terminal_classification,
            "rationale": advice.rationale,
            "advisory_only": True,
        }
    attempts.append(attempt)
    receipt["attempts"] = attempts
    receipt["recovery_attempts"] = len(attempts)
    recovery.receipt = receipt
    recovery.updated_at = datetime.now(UTC)
    db.commit()
    if method == "structural_repair":
        result = sanitize_pdf(content)
        recovered_filename = f"{Path(original.filename).stem[:160]}-sanitized.pdf"
        recovered_media_type = "application/pdf"
        recovery_mode = "hermes-inert-pdf-v1"
        removed = result.removed
        text_equivalent = True
    elif method == "independent_parser":
        result = recover_pdf_as_inert_text(content)
        recovered_filename = f"{Path(original.filename).stem[:160]}-recovered.txt"
        recovered_media_type = "text/plain"
        recovery_mode = "hermes-pdfium-text-v1"
        removed = {}
        text_equivalent = False
    else:
        result = recover_pdf_with_offline_ocr(content)
        recovered_filename = f"{Path(original.filename).stem[:160]}-ocr.txt"
        recovered_media_type = "text/plain"
        recovery_mode = "hermes-offline-ocr-v1"
        removed = {}
        text_equivalent = False
    recovered_content = result.content
    recovered_digest = (
        result.sanitized_digest
        if method == "structural_repair"
        else result.recovered_digest
    )
    reference = store.put(recovered_content, expected_digest=recovered_digest)
    sanitized = db.scalar(
        select(ScientificIngestionJob).where(
            ScientificIngestionJob.content_digest == recovered_digest
        )
    )
    if sanitized is None:
        now = datetime.now(UTC)
        source = dict(original.source)
        source["title"] = f"{source['title']} [inert recovered edition]"[:500]
        source["origin"] = f"{source['origin']}#{recovery_mode}"[:2000]
        source["edition_label"] = f"recovered-{recovered_digest[:12]}"
        sanitized = ScientificIngestionJob(
            schema_version="scientific-ingestion-v1.0.0",
            project=original.project,
            filename=recovered_filename,
            media_type=recovered_media_type,
            content_digest=recovered_digest,
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
                        "artifact_digest": recovered_digest,
                        "byte_size": len(recovered_content),
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
    attempt["completed_at"] = datetime.now(UTC).isoformat()
    attempt["derived_digest"] = recovered_digest
    attempt["pipeline_status"] = sanitized.status
    receipt = {
        "schema_version": "pdf-sanitization-receipt-v1.0.0",
        "original_job_id": str(original.id),
        "original_digest": result.original_digest,
        "original_retained": True,
        "sanitized_job_id": str(sanitized.id),
        "sanitized_digest": recovered_digest,
        "sanitizer": recovery_mode,
        "page_count": result.page_count,
        "text_digest": result.text_digest,
        "text_equivalent": text_equivalent,
        "visual_sample_digest": result.visual_sample_digest,
        "visual_sample_pages": result.visual_sample_pages,
        "visual_samples_equivalent": True,
        "removed": removed,
        "normal_pipeline_status": sanitized.status,
        "recovery_attempts": len(attempts),
        "attempts": attempts,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    recovery = db.get(ScientificIngestionRecovery, recovery_id)
    if recovery is None:
        raise RuntimeError("recovery record is unavailable after publication")
    recovery.sanitized_job_id = sanitized.id
    if sanitized.status == "published":
        recovery.status = "recovered"
    elif _latest_reason(sanitized) == "document contains instruction-injection content":
        recovery.status = "rejected"
        receipt["terminal_classification"] = "security_blocked"
        receipt["founder_action"] = _founder_action("security_blocked")
        receipt["redacted_edition_proposal"] = {
            "schema_version": "provenance-redaction-proposal-v1.0.0",
            "original_job_id": str(original.id),
            "original_digest": original.content_digest,
            "candidate_job_id": str(sanitized.id),
            "candidate_digest": recovered_digest,
            "scanner_finding": _latest_reason(sanitized),
            "proposed_action": "create_reviewed_redacted_edition",
            "automatic_execution": False,
            "founder_approval_required": True,
            "publication_authorized": False,
        }
    elif any(item not in attempted_methods + [method] for item in _METHODS):
        recovery.status = "queued"
        receipt["next_attempt_pending"] = True
    else:
        recovery.status = "rejected"
        receipt["terminal_classification"] = deterministic_terminal_classification(
            rejection_reason=_latest_reason(sanitized) or "recovery pipeline rejected",
            attempted_methods=attempted_methods + [method],
        )
        receipt["founder_action"] = _founder_action(receipt["terminal_classification"])
    recovery.receipt = receipt
    recovery.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(recovery)
    return recovery


def requeue_recoverable_outcomes(db: Session) -> int:
    """Retry proven inert editions and allow one independent-parser fallback."""

    records = list(
        db.scalars(
            select(ScientificIngestionRecovery).where(
                ScientificIngestionRecovery.status.in_(
                    ["rejected", "remediation_required"]
                )
            )
        ).all()
    )
    requeued = 0
    now = datetime.now(UTC)
    for record in records:
        original = db.get(ScientificIngestionJob, record.original_job_id)
        if original is None or original.status != "rejected":
            continue
        receipt = dict(record.receipt)
        if receipt.get("terminal_classification"):
            continue
        sanitized = (
            db.get(ScientificIngestionJob, record.sanitized_job_id)
            if record.sanitized_job_id
            else None
        )
        if sanitized is not None and sanitized.status == "published":
            receipt["normal_pipeline_status"] = "published"
            receipt["completed_at"] = now.isoformat()
            receipt["reconciled_after_remediation"] = True
            record.receipt = receipt
            record.status = "recovered"
            record.updated_at = now
            continue
        if not receipt.get("attempts"):
            receipt["legacy_recovery_attempts"] = int(
                receipt.get("recovery_attempts", 0)
            )
            receipt["recovery_attempts"] = 0
            receipt["controller_version"] = "bounded-recovery-v1"
            receipt["controller_adopted_at"] = now.isoformat()
            record.receipt = receipt
            record.status = "queued"
            record.updated_at = now
            requeued += 1
            continue
    db.commit()
    return requeued


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


def _latest_stage(job: ScientificIngestionJob) -> str | None:
    stages = job.stage_report.get("stages", [])
    return stages[-1].get("stage") if stages else None


_METHODS: tuple[RecoveryMethod, ...] = (
    "structural_repair",
    "independent_parser",
    "offline_ocr",
)


def _founder_action(classification: str) -> str:
    return {
        "replacement_required": "Provide a different source edition.",
        "security_blocked": (
            "Review a provenance-preserving redacted-edition proposal; scanner findings "
            "remain binding."
        ),
        "unsupported_format": "Convert the source using an approved format adapter.",
        "corrupt_unrecoverable": "Provide a verified replacement or request manual review.",
        "manual_review_required": "Review bounded diagnostics and approve a new method.",
    }[classification]
