from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pipeline import IngestionRejected, ScientificIngestionPipeline
from app.models.ingestion import ScientificIngestionJob
from app.schemas.evidence import EvidenceObjectCreate
from app.schemas.ingestion import (
    CoordinateReplayResponse,
    ScientificIngestionCreate,
    ScientificIngestionResponse,
)
from app.services.evidence import (
    EvidenceAccessContext,
    canonical_payload_digest,
    get_evidence_object,
    register_evidence_object,
)
from app.services.object_store import EvidenceObjectStore, ObjectReference


def quarantine_ingestion(
    db: Session,
    payload: ScientificIngestionCreate,
    store: EvidenceObjectStore,
    *,
    max_bytes: int,
) -> ScientificIngestionJob:
    content = payload.content_bytes()
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Scientific artifact is too large.")
    actual = hashlib.sha256(content).hexdigest()
    if actual != payload.content_digest:
        raise HTTPException(status_code=422, detail="Scientific artifact digest mismatch.")
    existing = db.scalar(
        select(ScientificIngestionJob).where(
            ScientificIngestionJob.content_digest == actual
        )
    )
    if existing is not None:
        return existing
    reference = store.put(content, expected_digest=actual)
    now = datetime.now(UTC)
    job = ScientificIngestionJob(
        schema_version=payload.schema_version,
        project=payload.project,
        filename=payload.filename,
        media_type=payload.media_type,
        content_digest=actual,
        quarantine_uri=reference.uri,
        access_class=payload.access_class,
        source=payload.source.model_dump(mode="json"),
        requested_by=payload.requested_by,
        status="quarantined",
        stage_report={
            "stages": [
                {
                    "stage": "quarantine",
                    "status": "passed",
                    "at": now.isoformat(),
                    "artifact_digest": actual,
                    "byte_size": len(content),
                }
            ]
        },
        published_object_ids=[],
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_ingestion(
    db: Session,
    job_id: UUID,
    store: EvidenceObjectStore,
    pipeline: ScientificIngestionPipeline,
) -> ScientificIngestionJob:
    job = db.get(ScientificIngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scientific ingestion job not found.")
    if job.status == "published":
        return job
    if job.status not in {"quarantined", "remediation_required"}:
        raise HTTPException(status_code=409, detail="Scientific ingestion is not processable.")
    content = store.get(
        ObjectReference(
            uri=job.quarantine_uri,
            content_digest=job.content_digest,
            byte_size=0,
        )
    )
    stages = list(job.stage_report.get("stages", []))
    try:
        report = pipeline.recover(job.filename, job.media_type, content)
        stages.extend(
            [
                _stage("scan", "passed", scanner=report.scanner),
                _stage("extract", "passed", pages=report.page_count),
                _stage(
                    "recover",
                    "passed",
                    objects=len(report.objects),
                    scanned=report.scanned,
                ),
                _stage("validate", "passed", warnings=report.warnings),
            ]
        )
        object_ids = _publish(db, job, report)
        stages.append(_stage("publish", "passed", objects=len(object_ids)))
        job.status = "published"
        job.published_object_ids = object_ids
        job.stage_report = {"stages": stages}
        job.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)
        return job
    except IngestionRejected as exc:
        db.rollback()
        job = db.get(ScientificIngestionJob, job_id)
        if job is None:
            raise RuntimeError("ingestion job vanished during rollback") from exc
        remediation = exc.remediation
        job.status = "remediation_required" if remediation else "rejected"
        stages.append(
            _stage(
                exc.stage,
                "needs_remediation" if remediation else "rejected",
                reason=str(exc)[:500],
            )
        )
        job.stage_report = {"stages": stages}
        job.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        job = db.get(ScientificIngestionJob, job_id)
        if job is None:
            raise RuntimeError("ingestion job vanished during rollback") from exc
        job.status = "remediation_required"
        stages.append(
            _stage(
                "publish",
                "needs_remediation",
                reason=type(exc).__name__,
            )
        )
        job.stage_report = {"stages": stages}
        job.published_object_ids = []
        job.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)
        return job


def replay_coordinate(
    db: Session,
    object_id: UUID,
    access: EvidenceAccessContext,
    store: EvidenceObjectStore,
    pipeline: ScientificIngestionPipeline,
) -> CoordinateReplayResponse:
    scientific = get_evidence_object(db, object_id, access)
    if scientific.object_type != "scientific_object":
        raise HTTPException(status_code=422, detail="Object has no scientific coordinates.")
    artifact_id = UUID(scientific.payload["artifact_object_id"])
    artifact = get_evidence_object(db, artifact_id, access)
    reference = ObjectReference(
        uri=artifact.payload["storage_uri"],
        content_digest=artifact.content_digest,
        byte_size=artifact.payload["byte_size"],
    )
    content = store.get(reference)
    suffix = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/markdown": ".md",
    }[artifact.payload["media_type"]]
    report = pipeline.recover(f"replay{suffix}", artifact.payload["media_type"], content)
    coordinates = scientific.payload["coordinates"]
    expected = scientific.payload.get("content_text")
    match = next(
        (
            item
            for item in report.objects
            if item.page == coordinates["page"]
            and item.line_start == coordinates["line_start"]
            and item.line_end == coordinates["line_end"]
            and item.scientific_type == scientific.payload["scientific_type"]
        ),
        None,
    )
    if match is None or match.text != expected:
        raise HTTPException(status_code=409, detail="Scientific coordinate replay failed.")
    replay_digest = hashlib.sha256(match.text.encode("utf-8")).hexdigest()
    return CoordinateReplayResponse(
        object_id=scientific.id,
        artifact_id=artifact.id,
        page=match.page,
        line_start=match.line_start,
        line_end=match.line_end,
        text=match.text,
        replay_digest=replay_digest,
    )


def ingestion_response(job: ScientificIngestionJob) -> ScientificIngestionResponse:
    return ScientificIngestionResponse.model_validate(job, from_attributes=True)


def _publish(db: Session, job: ScientificIngestionJob, report) -> list[UUID]:
    access = EvidenceAccessContext(
        actor=job.requested_by,
        projects=frozenset({job.project}),
        max_access_class=job.access_class,
        may_write=True,
    )
    source_id = _id(job.id, "source")
    edition_id = _id(job.id, "edition")
    artifact_id = _id(job.id, "artifact")
    source_payload = {
        "kind": "source",
        "title": job.source["title"],
        "origin": job.source["origin"],
        "rights": job.source["rights"],
        "acquired_at": job.source["acquired_at"],
    }
    edition_payload = {
        "kind": "edition",
        "source_object_id": str(source_id),
        "edition_label": job.source["edition_label"],
        "published_at": None,
    }
    artifact_payload = {
        "kind": "artifact",
        "edition_object_id": str(edition_id),
        "media_type": job.media_type,
        "storage_uri": job.quarantine_uri,
        "byte_size": _store_size(job),
        "artifact_digest": job.content_digest,
    }
    records = [
        _create(job, source_id, "source", "primary", source_payload),
        _create(job, edition_id, "edition", "primary", edition_payload),
        _create(
            job,
            artifact_id,
            "artifact",
            "primary",
            artifact_payload,
            digest=job.content_digest,
        ),
    ]
    object_ids = [source_id, edition_id, artifact_id]
    recovered_ids = [_id(job.id, f"scientific:{index}") for index in range(len(report.objects))]
    for index, item in enumerate(report.objects):
        parent_id = (
            recovered_ids[item.parent_index] if item.parent_index is not None else None
        )
        recovered_payload = {
            "kind": "scientific_object",
            "artifact_object_id": str(artifact_id),
            "scientific_type": item.scientific_type,
            "parent_object_id": str(parent_id) if parent_id else None,
            "coordinates": {
                "page": item.page,
                "line_start": item.line_start,
                "line_end": item.line_end,
            },
            "extraction_method": report.parser,
            "extraction_confidence": item.confidence,
            "content_text": item.text,
        }
        records.append(
            _create(
                job,
                recovered_ids[index],
                "scientific_object",
                "derived",
                recovered_payload,
            )
        )
        object_ids.append(recovered_ids[index])
    for record in records:
        register_evidence_object(db, record, access, commit=False)
    return object_ids


def _create(
    job: ScientificIngestionJob,
    object_id: UUID,
    object_type: str,
    authority_class: str,
    payload: dict,
    *,
    digest: str | None = None,
) -> EvidenceObjectCreate:
    native_id = f"ingestion:{job.id}:{object_type}:{object_id}"
    content_digest = digest or canonical_payload_digest(payload)
    return EvidenceObjectCreate.model_validate(
        {
            "schema_version": "canonical-identity-v1.0.0",
            "object_schema_version": "canonical-evidence-v1.0.0",
            "object_id": object_id,
            "object_type": object_type,
            "content_version": "1",
            "content_digest": content_digest,
            "producer": {
                "system": "hermes-ingestion",
                "native_type": object_type,
                "native_id": native_id,
                "schema_version": "scientific-ingestion-v1.0.0",
            },
            "aliases": [
                {
                    "namespace": "hermes-ingestion",
                    "object_type": object_type,
                    "value": native_id,
                }
            ],
            "supersedes_object_id": None,
            "project": job.project,
            "access_class": job.access_class,
            "authority_class": authority_class,
            "payload": payload,
            "created_by": job.requested_by,
        }
    )


def _id(job_id: UUID, name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"hermes-ingestion:{job_id}:{name}")


def _stage(stage: str, status: str, **detail) -> dict:
    return {
        "stage": stage,
        "status": status,
        "at": datetime.now(UTC).isoformat(),
        **detail,
    }


def _store_size(job: ScientificIngestionJob) -> int:
    stages = job.stage_report.get("stages", [])
    quarantine = next(item for item in stages if item["stage"] == "quarantine")
    return int(quarantine["byte_size"])
