from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pipeline import contains_instruction_injection
from app.models.retrieval import EvidenceRetrievalProjection
from app.models.surveillance import (
    SurveillanceDigest,
    SurveillanceFetchReceipt,
    SurveillancePublication,
    SurveillanceRoutingEvent,
    SurveillanceSource,
)
from app.schemas.surveillance import (
    CandidateDispositionCreate,
    FeedEntry,
    SourcePollCreate,
    SurveillanceSourceCreate,
    WeeklyDigestCreate,
)

_WORD = re.compile(r"[a-z0-9][a-z0-9-]+")


def _digest(document: object) -> str:
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def register_source(
    db: Session, payload: SurveillanceSourceCreate
) -> SurveillanceSource:
    existing = db.scalar(
        select(SurveillanceSource).where(
            SurveillanceSource.source_key == payload.source_key
        )
    )
    values = payload.model_dump(mode="json")
    values["feed_url"] = str(payload.feed_url)
    if existing is not None:
        current = {key: getattr(existing, key) for key in values}
        if current == values:
            return existing
        raise HTTPException(status_code=409, detail="Surveillance source is immutable.")
    source = SurveillanceSource(**values)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def poll_source(
    db: Session, source_id: UUID, payload: SourcePollCreate
) -> SurveillanceFetchReceipt:
    source = db.get(SurveillanceSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Surveillance source not found.")
    if not source.is_enabled:
        raise HTTPException(status_code=409, detail="Surveillance source is disabled.")

    receipt_document = {
        "schema_version": "surveillance-fetch-v1.0.0",
        "source_id": str(source.id),
        "requested_by": payload.requested_by,
        "connector_version": payload.connector_version,
        "fetched_at": payload.fetched_at,
        "http_status": payload.http_status,
        "entries": [entry.model_dump(mode="json") for entry in payload.entries],
    }
    receipt_digest = _digest(receipt_document)
    previous = db.scalar(
        select(SurveillanceFetchReceipt).where(
            SurveillanceFetchReceipt.receipt_digest == receipt_digest
        )
    )
    if previous is not None:
        return previous

    if payload.http_status >= 400:
        receipt = _receipt(
            source,
            payload,
            receipt_digest,
            status="failed",
            error_code="upstream_unavailable",
        )
        db.add(receipt)
        db.commit()
        db.refresh(receipt)
        return receipt

    new_count = duplicate_count = rejected_count = 0
    for entry in payload.entries:
        if contains_instruction_injection(f"{entry.title}\n{entry.abstract}"):
            rejected_count += 1
            continue
        entry_digest = _entry_digest(source.id, entry)
        if (
            db.scalar(
                select(SurveillancePublication.id).where(
                    SurveillancePublication.content_digest == entry_digest
                )
            )
            is not None
        ):
            duplicate_count += 1
            continue
        previous_version = _previous_version(db, source.id, entry)
        assessment = assess_entry(db, source, entry)
        publication = SurveillancePublication(
            project=source.project,
            source_id=source.id,
            external_id=entry.external_id,
            title=entry.title,
            canonical_url=str(entry.canonical_url),
            published_at=entry.published_at,
            publication_status=entry.status,
            content_digest=entry_digest,
            provenance={
                "schema_version": "surveillance-publication-v1.0.0",
                "source_key": source.source_key,
                "fetch_receipt_digest": receipt_digest,
                "external_id": entry.external_id,
                "doi": entry.doi,
                "authors": entry.authors,
                "abstract_digest": hashlib.sha256(entry.abstract.encode()).hexdigest(),
                "rights": source.rights,
                "access_class": source.access_class,
                "fetched_at": payload.fetched_at.isoformat(),
            },
            assessment=assessment,
            routing=_route(source, entry, assessment),
            supersedes_id=previous_version.id if previous_version else None,
        )
        db.add(publication)
        new_count += 1

    receipt = _receipt(
        source,
        payload,
        receipt_digest,
        status="succeeded",
        new_count=new_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def assess_entry(db: Session, source: SurveillanceSource, entry: FeedEntry) -> dict:
    candidate_tokens = _tokens(f"{entry.title} {entry.abstract}")
    comparison = (
        select(EvidenceRetrievalProjection.content_text)
        .where(EvidenceRetrievalProjection.project == source.project)
        .union_all(
            select(SurveillancePublication.title).where(
                SurveillancePublication.project == source.project
            )
        )
        .limit(1000)
    )
    existing = db.scalars(comparison).all()
    nearest = 0.0
    nearest_digest = None
    for title in existing:
        known = _tokens(title)
        union = candidate_tokens | known
        similarity = len(candidate_tokens & known) / len(union) if union else 0
        if similarity > nearest:
            nearest = similarity
            nearest_digest = hashlib.sha256(title.encode()).hexdigest()
    novelty = round(1.0 - nearest, 6)
    quality = 0.5
    quality += 0.15 if entry.doi else 0
    quality += 0.15 if entry.authors else 0
    quality += 0.1 if len(entry.abstract) >= 300 else 0
    quality += 0.1 if source.access_class == "public" else 0
    return {
        "schema_version": "surveillance-assessment-v1.0.0",
        "novelty_score": min(round(quality * 0 + novelty, 6), 1.0),
        "nearest_prior_similarity": round(nearest, 6),
        "nearest_prior_text_digest": nearest_digest,
        "comparison_basis": {
            "project": source.project,
            "projection": "canonical-scientific",
            "records_compared": len(existing),
            "includes_internal_memory": True,
        },
        "evidence_quality": min(round(quality, 6), 1.0),
        "technique_brief": {
            "title": entry.title,
            "applicability_domains": source.domains,
            "requires_independent_validation": True,
            "limitations": [
                "abstract-only surveillance evidence",
                "publication status does not establish institutional validity",
            ],
        },
        "contradiction_review_required": True,
        "adoption_authority": False,
    }


def dispose_candidate(
    db: Session, publication_id: UUID, payload: CandidateDispositionCreate
) -> dict:
    publication = db.get(SurveillancePublication, publication_id)
    if publication is None:
        raise HTTPException(
            status_code=404, detail="Surveillance publication not found."
        )
    proposal = {
        "schema_version": "surveillance-routing-proposal-v1.0.0",
        "publication_id": str(publication.id),
        "publication_digest": publication.content_digest,
        "decision": payload.decision,
        "decided_by": payload.decided_by,
        "rationale": payload.rationale,
        "target": publication.routing["target"],
        "proposed_question": publication.routing["proposed_question"],
        "approval_required": True,
        "execution_authority": False,
    }
    event_digest = _digest(proposal)
    existing = db.scalar(
        select(SurveillanceRoutingEvent).where(
            SurveillanceRoutingEvent.event_digest == event_digest
        )
    )
    if existing is None:
        existing = SurveillanceRoutingEvent(
            publication_id=publication.id,
            decision=payload.decision,
            decided_by=payload.decided_by,
            rationale=payload.rationale,
            proposal=proposal,
            event_digest=event_digest,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return {
        "event_id": existing.id,
        "event_digest": event_digest,
        "publication_id": publication.id,
        "decision": payload.decision,
        "approval_required": True,
        "proposal": proposal,
    }


def create_weekly_digest(
    db: Session, payload: WeeklyDigestCreate
) -> SurveillanceDigest:
    week_ending = (
        payload.week_ending + timedelta(days=6 - payload.week_ending.weekday())
    ).replace(hour=23, minute=59, second=59, microsecond=999999)
    start = week_ending - timedelta(days=7)
    items = list(
        db.scalars(
            select(SurveillancePublication)
            .where(SurveillancePublication.project == payload.project)
            .where(SurveillancePublication.created_at > start)
            .where(SurveillancePublication.created_at <= week_ending)
            .order_by(SurveillancePublication.content_digest)
        ).all()
    )
    body = {
        "schema_version": "surveillance-weekly-digest-v1.0.0",
        "project": payload.project,
        "week_ending": week_ending.isoformat(),
        "candidates": [
            {
                "publication_id": str(item.id),
                "content_digest": item.content_digest,
                "title": item.title,
                "status": item.publication_status,
                "novelty_score": item.assessment["novelty_score"],
                "evidence_quality": item.assessment["evidence_quality"],
                "citation": item.provenance,
                "routing": item.routing,
            }
            for item in items
        ],
        "authority": {
            "approval_required": True,
            "auto_adoption": False,
            "auto_trial": False,
        },
    }
    digest_sha256 = _digest(body)
    existing = db.scalar(
        select(SurveillanceDigest).where(
            SurveillanceDigest.digest_sha256 == digest_sha256
        )
    )
    if existing is not None:
        return existing
    record = SurveillanceDigest(
        project=payload.project,
        week_ending=week_ending,
        candidate_count=len(items),
        correction_count=sum(item.publication_status == "corrected" for item in items),
        retraction_count=sum(item.publication_status == "retracted" for item in items),
        digest=body,
        digest_sha256=digest_sha256,
        created_by=payload.requested_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def replay_publication(db: Session, publication_id: UUID) -> dict:
    item = db.get(SurveillancePublication, publication_id)
    if item is None:
        raise HTTPException(
            status_code=404, detail="Surveillance publication not found."
        )
    receipt = db.scalar(
        select(SurveillanceFetchReceipt).where(
            SurveillanceFetchReceipt.receipt_digest
            == item.provenance["fetch_receipt_digest"]
        )
    )
    return {
        "publication_id": item.id,
        "content_digest": item.content_digest,
        "source_id": item.source_id,
        "external_id": item.external_id,
        "canonical_url": item.canonical_url,
        "publication_status": item.publication_status,
        "provenance": item.provenance,
        "fetch_receipt_available": receipt is not None,
        "exact_replay": receipt is not None,
    }


def _receipt(
    source: SurveillanceSource,
    payload: SourcePollCreate,
    digest: str,
    *,
    status: str,
    new_count: int = 0,
    duplicate_count: int = 0,
    rejected_count: int = 0,
    error_code: str | None = None,
) -> SurveillanceFetchReceipt:
    return SurveillanceFetchReceipt(
        source_id=source.id,
        requested_by=payload.requested_by,
        connector_version=payload.connector_version,
        fetched_at=payload.fetched_at,
        http_status=payload.http_status,
        status=status,
        entry_count=len(payload.entries),
        new_count=new_count,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        receipt_digest=digest,
        error_code=error_code,
    )


def _entry_digest(source_id: UUID, entry: FeedEntry) -> str:
    return _digest({"source_id": str(source_id), **entry.model_dump(mode="json")})


def _previous_version(
    db: Session, source_id: UUID, entry: FeedEntry
) -> SurveillancePublication | None:
    target = (
        entry.corrects_external_id or entry.retracts_external_id or entry.external_id
    )
    return db.scalar(
        select(SurveillancePublication)
        .where(SurveillancePublication.source_id == source_id)
        .where(SurveillancePublication.external_id == target)
        .order_by(SurveillancePublication.created_at.desc())
    )


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _route(source: SurveillanceSource, entry: FeedEntry, assessment: dict) -> dict:
    domain = source.domains[0]
    target = {
        "machine-learning": "ml-method-review",
        "portfolio": "portfolio-risk-review",
        "risk": "portfolio-risk-review",
        "execution": "execution-method-review",
        "market-microstructure": "execution-method-review",
    }.get(domain, "research-program-proposal")
    return {
        "schema_version": "surveillance-routing-v1.0.0",
        "target": target,
        "proposed_question": f"Should {entry.title} be independently evaluated for {domain}?",
        "priority_score": round(
            assessment["novelty_score"] * assessment["evidence_quality"], 6
        ),
        "approval_required": True,
        "execution_authority": False,
    }
