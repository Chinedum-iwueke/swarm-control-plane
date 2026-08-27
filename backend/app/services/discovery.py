from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.discovery import DiscoveryMap, DiscoveryMapEvent
from app.models.evidence import CanonicalEvidenceObject
from app.models.lake_operations import LakeOperationEvent
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.models.research import ResearchDailyCycle
from app.schemas.discovery import DiscoveryMapCreate, DiscoveryMapDocument
from app.services.research import record_digest


class DiscoveryConflict(RuntimeError):
    pass


def semantic_fingerprint(document: DiscoveryMapDocument) -> str:
    population = document.population
    value = {
        "question": " ".join(document.question.lower().split()),
        "instruments": sorted(population.instruments),
        "venues": sorted(population.venue_keys),
        "start_at": population.start_at.isoformat(),
        "end_at": population.end_at.isoformat(),
        "timeframe": population.timeframe,
        "metric": document.effect.metric,
        "baseline": " ".join(document.baseline_definition.lower().split()),
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def register_discovery_map(db: Session, payload: DiscoveryMapCreate) -> DiscoveryMap:
    if record_digest(payload.document) != payload.map_digest:
        raise DiscoveryConflict("Map digest does not match the canonical document.")
    document = payload.document
    if db.get(ResearchDailyCycle, document.source_daily_cycle_id) is None:
        raise DiscoveryConflict("Source daily-research cycle does not exist.")
    catalog = db.scalar(
        select(MarketDataCatalogSnapshot).where(
            MarketDataCatalogSnapshot.catalog_digest
            == document.population.data_catalog_digest
        )
    )
    if catalog is None:
        raise DiscoveryConflict("Bound market-data catalog does not exist.")
    admission = db.scalar(
        select(LakeOperationEvent).where(
            LakeOperationEvent.event_digest
            == document.population.lake_admission_event_digest
        )
    )
    if (
        admission is None
        or admission.event_type != "admission_decision"
        or admission.detail.get("allowed") is not True
    ):
        raise DiscoveryConflict("Bound lake admission is absent or denied.")
    evidence = list(
        db.scalars(
            select(CanonicalEvidenceObject).where(
                CanonicalEvidenceObject.id.in_(document.evidence_object_ids)
            )
        ).all()
    )
    if len(evidence) != len(document.evidence_object_ids):
        raise DiscoveryConflict("One or more evidence objects do not exist.")
    if {item.content_digest for item in evidence} != set(document.evidence_digests):
        raise DiscoveryConflict("Evidence IDs and digests do not match.")
    if document.stage == "opportunity":
        producers = {
            json.dumps(item.producer, sort_keys=True, separators=(",", ":"))
            for item in evidence
        }
        if len(producers) < 2:
            raise DiscoveryConflict(
                "Opportunity evidence is not independently produced."
            )
    fingerprint = semantic_fingerprint(payload.document)
    existing = db.scalar(
        select(DiscoveryMap).where(
            DiscoveryMap.semantic_fingerprint == fingerprint,
            DiscoveryMap.status == "active",
        )
    )
    if existing is not None and existing.id != payload.supersedes_map_id:
        raise DiscoveryConflict("An active semantic duplicate already exists.")

    prior = None
    if payload.supersedes_map_id is not None:
        prior = db.scalar(
            select(DiscoveryMap)
            .where(DiscoveryMap.id == payload.supersedes_map_id)
            .with_for_update()
        )
        if prior is None:
            raise DiscoveryConflict("Superseded map does not exist.")
        if prior.status != "active":
            raise DiscoveryConflict("Superseded map is not active.")
        prior.status = "superseded"

    record = DiscoveryMap(
        map_key=payload.map_key,
        stage=payload.document.stage,
        document=payload.document.model_dump(mode="json"),
        map_digest=payload.map_digest,
        semantic_fingerprint=fingerprint,
        supersedes_map_id=payload.supersedes_map_id,
        status="active",
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    _event(
        db,
        record,
        "map_registered",
        {"stage": record.stage, "map_digest": record.map_digest},
        payload.registered_by,
    )
    if prior is not None:
        _event(
            db,
            prior,
            "map_superseded",
            {
                "replacement_map_id": str(record.id),
                "replacement_digest": record.map_digest,
            },
            payload.registered_by,
        )
    return record


def _event(
    db: Session, record: DiscoveryMap, event_type: str, detail: dict, actor: str
) -> DiscoveryMapEvent:
    previous = db.scalar(
        select(DiscoveryMapEvent)
        .where(DiscoveryMapEvent.map_id == record.id)
        .order_by(DiscoveryMapEvent.recorded_at.desc(), DiscoveryMapEvent.id.desc())
        .limit(1)
    )
    previous_digest = previous.event_digest if previous else None
    event_digest = record_digest(
        {
            "map_id": str(record.id),
            "event_type": event_type,
            "detail": detail,
            "previous_event_digest": previous_digest,
            "recorded_by": actor,
        }
    )
    event = DiscoveryMapEvent(
        map_id=record.id,
        event_type=event_type,
        detail=detail,
        previous_event_digest=previous_digest,
        event_digest=event_digest,
        recorded_by=actor,
    )
    db.add(event)
    return event
