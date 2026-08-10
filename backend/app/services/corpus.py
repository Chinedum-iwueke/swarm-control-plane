from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.corpus import CorpusBackup, CorpusRecoveryRun, CorpusSecurityFinding
from app.models.evidence import (
    CanonicalEvidenceEdge,
    CanonicalEvidenceObject,
    CanonicalIdentityAlias,
)
from app.models.ingestion import ScientificIngestionJob
from app.models.retrieval import EvidenceRetrievalProjection, EvidenceRetrievalState
from app.schemas.corpus import CorpusBackupCreate
from app.services.object_store import EvidenceObjectStore, ObjectReference
from app.services.retrieval import PROJECTION_NAME, build_projections, corpus_digest

BACKUP_SCHEMA_VERSION = "corpus-backup-v1.0.0"
_SAFE_FINDINGS = {
    "active_content": ("high", "quarantined"),
    "malware": ("critical", "quarantined"),
    "instruction_injection": ("high", "quarantined"),
    "archive": ("high", "quarantined"),
    "parser_limit": ("medium", "remediation_required"),
    "invalid_container": ("medium", "quarantined"),
    "artifact_missing": ("high", "remediation_required"),
    "integrity_failure": ("critical", "quarantined"),
}


def finding_code(stage: str, reason: str) -> str:
    normalized = reason.lower()
    if "instruction-injection" in normalized:
        return "instruction_injection"
    if "malware" in normalized or "signature" in normalized:
        return "malware"
    if "active pdf" in normalized:
        return "active_content"
    if "archive" in normalized:
        return "archive"
    if "limit" in normalized or "outside" in normalized:
        return "parser_limit"
    if stage in {"scan", "quarantine"}:
        return "invalid_container"
    return "integrity_failure"


def record_security_finding(
    db: Session,
    job: ScientificIngestionJob,
    *,
    code: str,
    stage: str,
) -> CorpusSecurityFinding:
    severity, disposition = _SAFE_FINDINGS[code]
    finding = CorpusSecurityFinding(
        ingestion_job_id=job.id,
        project=job.project,
        finding_code=code,
        stage=stage,
        severity=severity,
        disposition=disposition,
        remediation={
            "action": "security_review" if severity in {"high", "critical"} else "curator_review",
            "raw_content_retained": True,
            "content_exposed": False,
        },
    )
    db.add(finding)
    return finding


def create_backup(
    db: Session,
    payload: CorpusBackupCreate,
    store: EvidenceObjectStore,
) -> CorpusBackup:
    objects = list(
        db.scalars(
            select(CanonicalEvidenceObject)
            .where(CanonicalEvidenceObject.project == payload.project)
            .order_by(CanonicalEvidenceObject.id)
        ).all()
    )
    object_ids = [item.id for item in objects]
    aliases = list(
        db.scalars(
            select(CanonicalIdentityAlias)
            .where(CanonicalIdentityAlias.canonical_object_id.in_(object_ids))
            .order_by(CanonicalIdentityAlias.id)
        ).all()
    ) if object_ids else []
    edges = list(
        db.scalars(
            select(CanonicalEvidenceEdge)
            .where(
                CanonicalEvidenceEdge.subject_id.in_(object_ids),
                CanonicalEvidenceEdge.object_id.in_(object_ids),
            )
            .order_by(CanonicalEvidenceEdge.id)
        ).all()
    ) if object_ids else []
    artifact_refs = sorted(
        {
            (item.payload["storage_uri"], item.content_digest, item.payload["byte_size"])
            for item in objects
            if item.object_type == "artifact"
        }
    )
    for uri, digest, size in artifact_refs:
        if not store.exists(ObjectReference(uri=uri, content_digest=digest, byte_size=size)):
            raise HTTPException(
                status_code=409,
                detail="Corpus backup blocked by unavailable artifact.",
            )
    document = {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "project": payload.project,
        "objects": [_object_document(item) for item in objects],
        "aliases": [_alias_document(item) for item in aliases],
        "edges": [_edge_document(item) for item in edges],
        "artifact_references": [
            {"uri": uri, "content_digest": digest, "byte_size": size}
            for uri, digest, size in artifact_refs
        ],
    }
    encoded = _canonical(document)
    manifest_digest = hashlib.sha256(encoded).hexdigest()
    existing = db.scalar(
        select(CorpusBackup).where(
            CorpusBackup.manifest_digest == manifest_digest
        )
    )
    if existing is not None:
        return existing
    reference = store.put(encoded, expected_digest=manifest_digest)
    backup = CorpusBackup(
        schema_version=BACKUP_SCHEMA_VERSION,
        project=payload.project,
        corpus_digest=_project_digest(document["objects"]),
        manifest_digest=manifest_digest,
        storage_uri=reference.uri,
        object_count=len(objects),
        artifact_count=len(artifact_refs),
        byte_size=len(encoded),
        created_by=payload.created_by,
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)
    return backup


def restore_backup(
    db: Session,
    backup_id: UUID,
    store: EvidenceObjectStore,
    requested_by: str,
) -> CorpusRecoveryRun:
    started = datetime.now(UTC)
    backup = db.get(CorpusBackup, backup_id)
    if backup is None:
        raise HTTPException(status_code=404, detail="Corpus backup not found.")
    existing = db.scalar(
        select(func.count())
        .select_from(CanonicalEvidenceObject)
        .where(CanonicalEvidenceObject.project == backup.project)
    ) or 0
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Corpus restore requires an empty project corpus.",
        )
    reference = ObjectReference(
        uri=backup.storage_uri,
        content_digest=backup.manifest_digest,
        byte_size=backup.byte_size,
    )
    try:
        encoded = store.get(reference)
        document = json.loads(encoded)
        _validate_manifest(document, backup)
        _validate_artifacts(document, store)
        supersession: list[tuple[UUID, UUID]] = []
        for item in document["objects"]:
            restored = _restore_object(item)
            predecessor = restored.pop("supersedes_object_id")
            db.add(CanonicalEvidenceObject(**restored, supersedes_object_id=None))
            if predecessor is not None:
                supersession.append((restored["id"], predecessor))
        db.flush()
        for object_id, predecessor_id in supersession:
            db.get(CanonicalEvidenceObject, object_id).supersedes_object_id = (
                predecessor_id
            )
        db.flush()
        for item in document["aliases"]:
            db.add(CanonicalIdentityAlias(**_restore_alias(item)))
        for item in document["edges"]:
            db.add(CanonicalEvidenceEdge(**_restore_edge(item)))
        db.commit()
        state = build_projections(db)
        evidence = {
            "requested_by": requested_by,
            "backup_manifest_digest": backup.manifest_digest,
            "restored_objects": len(document["objects"]),
            "restored_aliases": len(document["aliases"]),
            "restored_edges": len(document["edges"]),
            "projection_corpus_digest": state.corpus_digest,
            "rpo_seconds": max(0.0, (started - backup.created_at).total_seconds()),
            "rto_seconds": max(0.0, (datetime.now(UTC) - started).total_seconds()),
        }
        return _recovery(db, "restore", backup.project, backup.id, started, evidence)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Corpus restore failed closed: {type(exc).__name__}.",
        ) from exc


def recover_projections(
    db: Session, project: str, requested_by: str
) -> CorpusRecoveryRun:
    started = datetime.now(UTC)
    db.execute(delete(EvidenceRetrievalProjection))
    db.execute(delete(EvidenceRetrievalState))
    db.commit()
    state = build_projections(db)
    evidence = {
        "requested_by": requested_by,
        "projection_name": state.projection_name,
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "object_count": state.object_count,
        "rebuild_seconds": max(0.0, (datetime.now(UTC) - started).total_seconds()),
    }
    return _recovery(db, "projection_rebuild", project, None, started, evidence)


def recover_queue(
    db: Session,
    project: str,
    store: EvidenceObjectStore,
    *,
    stale_after_seconds: int,
    requested_by: str,
) -> CorpusRecoveryRun:
    started = datetime.now(UTC)
    cutoff = started - timedelta(seconds=stale_after_seconds)
    jobs = list(
        db.scalars(
            select(ScientificIngestionJob).where(
                ScientificIngestionJob.project == project,
                ScientificIngestionJob.status.in_(("quarantined", "remediation_required")),
                ScientificIngestionJob.updated_at <= cutoff,
            )
        ).all()
    )
    requeued = 0
    missing = 0
    for job in jobs:
        reference = ObjectReference(
            uri=job.quarantine_uri,
            content_digest=job.content_digest,
            byte_size=0,
        )
        if store.exists(reference):
            job.status = "quarantined"
            job.updated_at = started
            requeued += 1
        else:
            job.status = "remediation_required"
            record_security_finding(
                db, job, code="artifact_missing", stage="queue_recovery"
            )
            missing += 1
    db.commit()
    evidence = {
        "requested_by": requested_by,
        "stale_jobs": len(jobs),
        "requeued_jobs": requeued,
        "missing_artifacts": missing,
        "recovery_seconds": max(0.0, (datetime.now(UTC) - started).total_seconds()),
    }
    return _recovery(db, "queue_recovery", project, None, started, evidence)


def corpus_health(
    db: Session, project: str, store: EvidenceObjectStore
) -> dict:
    now = datetime.now(UTC)
    objects = list(
        db.scalars(
            select(CanonicalEvidenceObject).where(
                CanonicalEvidenceObject.project == project
            )
        ).all()
    )
    jobs = list(
        db.scalars(
            select(ScientificIngestionJob).where(
                ScientificIngestionJob.project == project
            )
        ).all()
    )
    missing = sum(
        not store.exists(
            ObjectReference(
                uri=item.payload["storage_uri"],
                content_digest=item.content_digest,
                byte_size=item.payload["byte_size"],
            )
        )
        for item in objects
        if item.object_type == "artifact"
    )
    object_store_bytes = sum(
        int(item.payload["byte_size"])
        for item in objects
        if item.object_type == "artifact"
    )
    state = db.get(EvidenceRetrievalState, PROJECTION_NAME)
    projection = "missing"
    lag = None
    if state is not None:
        lag = max(0.0, (now - state.built_at).total_seconds())
        try:
            projection = "stale" if state.corpus_digest != corpus_digest(db) else "healthy"
        except (KeyError, TypeError, ValueError):
            projection = "corrupt"
    latest_backup = db.scalar(
        select(CorpusBackup)
        .where(CorpusBackup.project == project)
        .order_by(CorpusBackup.created_at.desc())
    )
    latest_restore = db.scalar(
        select(CorpusRecoveryRun)
        .where(
            CorpusRecoveryRun.project == project,
            CorpusRecoveryRun.operation == "restore",
            CorpusRecoveryRun.status == "succeeded",
        )
        .order_by(CorpusRecoveryRun.ended_at.desc())
    )
    findings = db.scalar(
        select(func.count())
        .select_from(CorpusSecurityFinding)
        .where(CorpusSecurityFinding.project == project)
    ) or 0
    backlog = sum(job.status in {"quarantined", "remediation_required"} for job in jobs)
    rejected = sum(job.status == "rejected" for job in jobs)
    backup_age = (
        max(0.0, (now - latest_backup.created_at).total_seconds())
        if latest_backup
        else None
    )
    restore_age = (
        max(0.0, (now - latest_restore.ended_at).total_seconds())
        if latest_restore
        else None
    )
    slo = {
        "artifacts_available": missing == 0,
        "projection_current": projection == "healthy",
        "backup_within_24h": backup_age is not None and backup_age <= 86_400,
        "restore_proof_within_30d": (
            restore_age is not None and restore_age <= 2_592_000
        ),
        "queue_backlog_below_100": backlog < 100,
    }
    return {
        "project": project,
        "observed_at": now,
        "canonical_objects": len(objects),
        "object_store_bytes": object_store_bytes,
        "ingestion_backlog": backlog,
        "rejected_jobs": rejected,
        "security_findings": findings,
        "missing_artifacts": missing,
        "projection_status": projection,
        "projection_lag_seconds": lag,
        "latest_backup_age_seconds": backup_age,
        "latest_restore_age_seconds": restore_age,
        "slo": slo,
        "healthy": all(slo.values()),
    }


def _recovery(db, operation, project, backup_id, started, evidence):
    ended = datetime.now(UTC)
    digest = hashlib.sha256(_canonical(evidence)).hexdigest()
    run = CorpusRecoveryRun(
        operation=operation,
        project=project,
        backup_id=backup_id,
        status="succeeded",
        evidence=evidence,
        evidence_digest=digest,
        error_code=None,
        started_at=started,
        ended_at=ended,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _object_document(item):
    return {
        "id": str(item.id),
        "schema_version": item.schema_version,
        "object_schema_version": item.object_schema_version,
        "object_type": item.object_type,
        "content_version": item.content_version,
        "content_digest": item.content_digest,
        "producer": item.producer,
        "supersedes_object_id": str(item.supersedes_object_id) if item.supersedes_object_id else None,
        "project": item.project,
        "access_class": item.access_class,
        "authority_class": item.authority_class,
        "payload": item.payload,
        "created_by": item.created_by,
    }


def _alias_document(item):
    return {
        "id": str(item.id),
        "canonical_object_id": str(item.canonical_object_id),
        "canonical_object_type": item.canonical_object_type,
        "namespace": item.namespace,
        "native_object_type": item.native_object_type,
        "alias_value": item.alias_value,
        "producer_schema_version": item.producer_schema_version,
    }


def _edge_document(item):
    return {
        "id": str(item.id),
        "subject_id": str(item.subject_id),
        "predicate": item.predicate,
        "object_id": str(item.object_id),
    }


def _restore_object(item):
    output = dict(item)
    output["id"] = UUID(output["id"])
    if output["supersedes_object_id"]:
        output["supersedes_object_id"] = UUID(output["supersedes_object_id"])
    return output


def _restore_alias(item):
    output = dict(item)
    output["id"] = UUID(output["id"])
    output["canonical_object_id"] = UUID(output["canonical_object_id"])
    return output


def _restore_edge(item):
    output = dict(item)
    for key in ("id", "subject_id", "object_id"):
        output[key] = UUID(output[key])
    return output


def _validate_manifest(document, backup):
    if document.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise ValueError("backup schema is incompatible")
    if document.get("project") != backup.project:
        raise ValueError("backup project mismatch")
    if hashlib.sha256(_canonical(document)).hexdigest() != backup.manifest_digest:
        raise ValueError("backup manifest digest mismatch")
    if _project_digest(document["objects"]) != backup.corpus_digest:
        raise ValueError("backup corpus digest mismatch")


def _validate_artifacts(document, store):
    for item in document["artifact_references"]:
        reference = ObjectReference(**item)
        if not store.exists(reference):
            raise ValueError("backup artifact is unavailable")
        store.get(reference)


def _project_digest(objects):
    return hashlib.sha256(_canonical(objects)).hexdigest()


def _canonical(document) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
