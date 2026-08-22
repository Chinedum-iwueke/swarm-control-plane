from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import ScientificIngestionJob, ScientificIngestionRecovery
from app.schemas.ingestion import (
    BlockedArtifactAttempt,
    BlockedArtifactRegisterEntry,
    BlockedArtifactRegisterResponse,
)

_BLOCKED_STATUSES = ("quarantined", "remediation_required", "rejected")


def blocked_artifact_register(db: Session) -> BlockedArtifactRegisterResponse:
    rows = db.execute(
        select(ScientificIngestionJob, ScientificIngestionRecovery)
        .outerjoin(
            ScientificIngestionRecovery,
            ScientificIngestionRecovery.original_job_id == ScientificIngestionJob.id,
        )
        .where(ScientificIngestionJob.status.in_(_BLOCKED_STATUSES))
        .order_by(ScientificIngestionJob.updated_at.desc())
    ).all()
    items = [
        _entry(job, recovery)
        for job, recovery in rows
        if recovery is None or recovery.status != "recovered"
    ]
    counts = Counter(item.classification for item in items)
    return BlockedArtifactRegisterResponse(
        generated_at=datetime.now(timezone.utc),
        total=len(items),
        counts_by_classification=dict(sorted(counts.items())),
        items=items,
    )


def _entry(
    job: ScientificIngestionJob,
    recovery: ScientificIngestionRecovery | None,
) -> BlockedArtifactRegisterEntry:
    receipt = recovery.receipt if recovery is not None else {}
    raw_attempts = receipt.get("attempts", [])
    attempts = [BlockedArtifactAttempt.model_validate(item) for item in raw_attempts]
    classification = receipt.get("terminal_classification")
    if not classification:
        classification = (
            "awaiting_recovery"
            if recovery is None or recovery.status in {"queued", "processing"}
            else "manual_review_required"
        )
    action = receipt.get("founder_action") or _default_action(classification)
    terminal = bool(receipt.get("terminal_classification"))
    source = job.source or {}
    return BlockedArtifactRegisterEntry(
        original_job_id=job.id,
        recovery_id=recovery.id if recovery is not None else None,
        project=job.project,
        filename=job.filename,
        media_type=job.media_type,
        content_digest=job.content_digest,
        source_title=str(source.get("title") or job.filename),
        source_origin=str(source.get("origin") or "unknown"),
        ingestion_status=job.status,
        recovery_status=recovery.status if recovery is not None else None,
        classification=classification,
        action_required=action,
        retry_eligible=not terminal,
        attempted_methods=[attempt.method for attempt in attempts],
        attempts=attempts,
        redacted_edition_proposal=receipt.get("redacted_edition_proposal"),
        created_at=job.created_at,
        updated_at=recovery.updated_at if recovery is not None else job.updated_at,
    )


def _default_action(classification: str) -> str:
    return {
        "awaiting_recovery": "Allow the bounded recovery steward to process this artifact.",
        "manual_review_required": "Review the retained quarantine evidence and recovery ledger.",
        "replacement_required": "Provide a different source edition.",
        "security_blocked": (
            "Review a provenance-preserving redacted-edition proposal; scanner findings "
            "remain binding."
        ),
        "unsupported_format": "Provide the source in an approved machine-readable format.",
        "corrupt_unrecoverable": "Provide an intact replacement artifact.",
    }.get(classification, "Review the retained quarantine evidence.")
