from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.models.reference_data import ReferenceDataSnapshot
from app.schemas.market_data_catalog import (
    ImmutableMarketDataCatalog,
    MarketDataCatalogCreate,
    MarketDataResolution,
    MarketDataResolveRequest,
)
from app.schemas.reference_data import (
    PointInTimeReferenceSnapshot,
    ReferenceResolveRequest,
)
from app.services.reference_data import resolve_snapshot
from app.services.research import record_digest


class MarketDataConflict(ValueError):
    pass


class MarketDataUnknown(LookupError):
    pass


def register_catalog(
    db: Session, payload: MarketDataCatalogCreate
) -> MarketDataCatalogSnapshot:
    if record_digest(payload.catalog) != payload.catalog_digest:
        raise MarketDataConflict("Market-data catalog digest does not match content.")
    reference = db.scalar(
        select(ReferenceDataSnapshot).where(
            ReferenceDataSnapshot.snapshot_digest
            == payload.catalog.reference_snapshot_digest
        )
    )
    if reference is None:
        raise MarketDataUnknown("Bound reference-data snapshot was not found.")
    _validate_reference_bindings(payload.catalog, reference)
    existing = db.scalar(
        select(MarketDataCatalogSnapshot).where(
            or_(
                MarketDataCatalogSnapshot.catalog_key == payload.catalog_key,
                MarketDataCatalogSnapshot.catalog_digest == payload.catalog_digest,
            )
        )
    )
    if existing is not None:
        if existing.catalog_digest == payload.catalog_digest:
            return existing
        raise MarketDataConflict("Market-data catalog key is already registered.")
    if payload.supersedes_catalog_id is not None:
        prior = db.get(MarketDataCatalogSnapshot, payload.supersedes_catalog_id)
        if prior is None:
            raise MarketDataUnknown("Superseded market-data catalog was not found.")
        if payload.catalog.as_of <= prior.as_of:
            raise MarketDataConflict(
                "A superseding catalog must advance the knowledge clock."
            )
    record = MarketDataCatalogSnapshot(
        catalog_key=payload.catalog_key,
        as_of=payload.catalog.as_of,
        catalog=payload.catalog.model_dump(mode="json"),
        catalog_digest=payload.catalog_digest,
        reference_snapshot_digest=payload.catalog.reference_snapshot_digest,
        supersedes_catalog_id=payload.supersedes_catalog_id,
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    return record


def _validate_reference_bindings(
    catalog: ImmutableMarketDataCatalog, reference: ReferenceDataSnapshot
) -> None:
    snapshot = PointInTimeReferenceSnapshot.model_validate(reference.snapshot)
    venues = {item.venue_id for item in snapshot.venues}
    instruments = {item.instrument_id for item in snapshot.instruments}
    listings = {
        (item.listing_id, item.venue_id, item.instrument_id)
        for item in snapshot.listings
    }
    for partition in catalog.partitions:
        if partition.venue_id not in venues:
            raise MarketDataConflict(
                "Partition venue is absent from the reference snapshot."
            )
        if partition.instrument_id not in instruments:
            raise MarketDataConflict(
                "Partition instrument is absent from the reference snapshot."
            )
        if (
            partition.listing_id,
            partition.venue_id,
            partition.instrument_id,
        ) not in listings:
            raise MarketDataConflict(
                "Partition listing binding conflicts with the reference snapshot."
            )
    if any(item.instrument_id not in instruments for item in catalog.memberships):
        raise MarketDataConflict(
            "Catalog membership is absent from the reference snapshot."
        )


def resolve_market_data(
    db: Session, request: MarketDataResolveRequest
) -> MarketDataResolution:
    statement = select(MarketDataCatalogSnapshot).where(
        MarketDataCatalogSnapshot.as_of <= request.known_at
    )
    if request.catalog_digest:
        statement = statement.where(
            MarketDataCatalogSnapshot.catalog_digest == request.catalog_digest
        )
    record = db.scalar(
        statement.order_by(MarketDataCatalogSnapshot.as_of.desc()).limit(1)
    )
    if record is None:
        raise MarketDataUnknown("No market-data catalog was known at that time.")
    catalog = ImmutableMarketDataCatalog.model_validate(record.catalog)
    reference = db.scalar(
        select(ReferenceDataSnapshot).where(
            ReferenceDataSnapshot.snapshot_digest == catalog.reference_snapshot_digest
        )
    )
    if reference is None or reference.as_of > request.known_at:
        raise MarketDataUnknown(
            "Bound reference identity was unavailable at that time."
        )
    identity = resolve_snapshot(
        PointInTimeReferenceSnapshot.model_validate(reference.snapshot),
        ReferenceResolveRequest(
            venue_id=request.venue_id,
            symbol=request.symbol,
            effective_at=request.effective_at,
            known_at=request.known_at,
            snapshot_digest=reference.snapshot_digest,
        ),
        snapshot_id=reference.id,
        snapshot_digest=reference.snapshot_digest,
    )
    partitions = [
        item
        for item in catalog.partitions
        if item.dataset_key == request.dataset_key
        and item.layer == request.layer
        and item.venue_id == request.venue_id
        and item.instrument_id == identity.instrument.instrument_id
        and item.listing_id == identity.listing.listing_id
        and item.timeframe == request.timeframe
        and item.event_start <= request.effective_at < item.event_end
        and item.available_at <= request.known_at
    ]
    if not partitions:
        raise MarketDataUnknown(
            "No point-in-time partition covers the requested clocks."
        )
    logical_keys = {item.partition_key for item in partitions}
    if len(logical_keys) != 1:
        raise MarketDataConflict("Market-data partition coverage is ambiguous.")
    partition = max(partitions, key=lambda item: (item.available_at, item.revision_id))
    if partition.duplicate_count or partition.gap_count:
        raise MarketDataUnknown(
            "Point-in-time partition failed duplicate or coverage-gap admission."
        )
    availability = [
        item
        for item in catalog.source_availability
        if item.source_key == partition.source_key
        and item.coverage_start <= request.effective_at < item.coverage_end
        and item.available_at <= request.known_at
    ]
    if not availability:
        raise MarketDataUnknown(
            "Source availability is unknown at the requested clocks."
        )
    source = max(availability, key=lambda item: (item.available_at, item.revision_id))
    if source.status != "available":
        raise MarketDataUnknown(f"Source was {source.status} at the requested clocks.")
    membership = None
    if request.universe_key:
        memberships = [
            item
            for item in catalog.memberships
            if item.universe_key == request.universe_key
            and item.instrument_id == identity.instrument.instrument_id
            and item.effective_from <= request.effective_at
            and (item.effective_to is None or request.effective_at < item.effective_to)
            and item.available_at <= request.known_at
        ]
        if not memberships:
            raise MarketDataUnknown(
                "Instrument membership is unknown at the requested clocks."
            )
        membership = max(
            memberships, key=lambda item: (item.available_at, item.revision_id)
        )
    return MarketDataResolution(
        catalog_id=record.id,
        catalog_digest=record.catalog_digest,
        catalog_as_of=record.as_of,
        reference_snapshot_digest=record.reference_snapshot_digest,
        effective_at=request.effective_at,
        known_at=request.known_at,
        instrument_id=identity.instrument.instrument_id,
        listing_id=identity.listing.listing_id,
        partition=partition,
        membership=membership,
        source_availability=source,
        claim_boundary=(
            "Exact catalog and reference digests; only content available by known_at "
            "is admitted. Missing, delayed, ambiguous, or future data fails closed."
        ),
    )
