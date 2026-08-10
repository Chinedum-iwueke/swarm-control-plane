from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corpus_sync import CorpusSyncItem, CorpusSyncRun
from app.models.ingestion import ScientificIngestionJob
from app.schemas.corpus_sync import CorpusSyncRunCreate, CorpusSyncRunResponse


def reconcile_corpus(db: Session, payload: CorpusSyncRunCreate) -> CorpusSyncRun:
    document = payload.model_dump(mode="json")
    inventory_digest = _digest(document)
    existing = db.scalar(
        select(CorpusSyncRun).where(CorpusSyncRun.inventory_digest == inventory_digest)
    )
    if existing is not None:
        return existing

    previous = db.scalar(
        select(CorpusSyncRun)
        .where(
            CorpusSyncRun.project == payload.project,
            CorpusSyncRun.source_kind == payload.source_kind,
            CorpusSyncRun.source_root == payload.source_root,
        )
        .order_by(CorpusSyncRun.created_at.desc())
    )
    previous_items = {
        item.source_locator: item
        for item in (
            db.scalars(
                select(CorpusSyncItem).where(CorpusSyncItem.run_id == previous.id)
            ).all()
            if previous
            else []
        )
    }
    prior_by_digest = {
        item.content_digest: item
        for item in previous_items.values()
        if item.content_digest and item.disposition in {"canonical", "duplicate"}
    }
    run = CorpusSyncRun(
        id=uuid4(),
        schema_version=payload.schema_version,
        project=payload.project,
        source_kind=payload.source_kind,
        source_root=payload.source_root,
        inventory_digest=inventory_digest,
        requested_by=payload.requested_by,
        status="reconciling",
        counts={},
        coverage_digest="0" * 64,
    )
    items: list[CorpusSyncItem] = []
    seen: set[str] = set()
    for proposed in payload.items:
        if proposed.source_locator in seen:
            raise HTTPException(
                status_code=422, detail="Source locators must be unique."
            )
        seen.add(proposed.source_locator)
        disposition = proposed.disposition
        job = _validated_job(db, payload, proposed)
        duplicate = prior_by_digest.get(proposed.content_digest)
        if disposition == "canonical" and duplicate is not None:
            disposition = "duplicate"
            job = db.get(ScientificIngestionJob, duplicate.ingestion_job_id)
        predecessor = previous_items.get(proposed.source_locator) or duplicate
        items.append(
            CorpusSyncItem(
                run_id=run.id,
                source_locator=proposed.source_locator,
                content_digest=proposed.content_digest,
                classification=proposed.classification,
                access_class=proposed.access_class,
                disposition=disposition,
                ingestion_job_id=job.id if job else proposed.ingestion_job_id,
                canonical_object_ids=[
                    str(value) for value in (job.published_object_ids if job else [])
                ],
                predecessor_item_id=predecessor.id if predecessor else None,
                detail=proposed.detail,
            )
        )
    for locator, prior in previous_items.items():
        if locator not in seen and prior.disposition not in {"excluded", "superseded"}:
            items.append(
                CorpusSyncItem(
                    run_id=run.id,
                    source_locator=locator,
                    content_digest=prior.content_digest,
                    classification=prior.classification,
                    access_class=prior.access_class,
                    disposition="superseded",
                    ingestion_job_id=prior.ingestion_job_id,
                    canonical_object_ids=prior.canonical_object_ids,
                    predecessor_item_id=prior.id,
                    detail="Source absent from the latest complete inventory; canonical evidence retained.",
                )
            )
    counts: dict[str, int] = {}
    for item in items:
        counts[item.disposition] = counts.get(item.disposition, 0) + 1
    run.counts = counts
    run.status = "attention_required" if counts.get("failed", 0) else "complete"
    run.coverage_digest = _digest(
        [
            {
                "source_locator": item.source_locator,
                "content_digest": item.content_digest,
                "disposition": item.disposition,
                "canonical_object_ids": item.canonical_object_ids,
            }
            for item in sorted(items, key=lambda value: value.source_locator)
        ]
    )
    db.add(run)
    db.flush()
    db.add_all(items)
    db.commit()
    db.refresh(run)
    return run


def corpus_sync_response(db: Session, run: CorpusSyncRun) -> CorpusSyncRunResponse:
    items = db.scalars(
        select(CorpusSyncItem)
        .where(CorpusSyncItem.run_id == run.id)
        .order_by(CorpusSyncItem.source_locator)
    ).all()
    return CorpusSyncRunResponse.model_validate(
        {
            **{
                key: getattr(run, key)
                for key in (
                    "id",
                    "schema_version",
                    "project",
                    "source_kind",
                    "source_root",
                    "inventory_digest",
                    "requested_by",
                    "status",
                    "counts",
                    "coverage_digest",
                    "created_at",
                )
            },
            "items": items,
        },
        from_attributes=True,
    )


def _validated_job(db: Session, run, item) -> ScientificIngestionJob | None:
    if item.ingestion_job_id is None:
        return None
    job = db.get(ScientificIngestionJob, item.ingestion_job_id)
    if (
        job is None
        or job.project != run.project
        or job.content_digest != item.content_digest
    ):
        raise HTTPException(
            status_code=422, detail="Ingestion evidence does not match inventory item."
        )
    expected = "published" if item.disposition == "canonical" else job.status
    if item.disposition == "canonical" and expected != job.status:
        raise HTTPException(status_code=409, detail="Canonical item is not published.")
    if item.disposition == "quarantined" and job.status not in {
        "quarantined",
        "remediation_required",
        "rejected",
    }:
        raise HTTPException(
            status_code=409, detail="Quarantine disposition is inconsistent."
        )
    return job


def _digest(document) -> str:
    return hashlib.sha256(
        json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()
