from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.lake_operations import LakeGovernanceSnapshot, LakeOperationEvent
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.schemas.lake_operations import (
    LakeAdmissionDecision,
    LakeAdmissionRequest,
    LakeGovernanceContract,
    LakeGovernanceCreate,
    PublicationActionRequest,
    PublicationState,
    RestoreRequest,
)
from app.schemas.market_data_catalog import ImmutableMarketDataCatalog
from app.services.research import record_digest


class LakeOperationConflict(ValueError):
    pass


class LakeOperationUnknown(LookupError):
    pass


def register_lake_governance(
    db: Session, payload: LakeGovernanceCreate
) -> LakeGovernanceSnapshot:
    if record_digest(payload.snapshot) != payload.snapshot_digest:
        raise LakeOperationConflict(
            "Lake-governance snapshot digest does not match content."
        )
    catalog = db.scalar(
        select(MarketDataCatalogSnapshot).where(
            MarketDataCatalogSnapshot.catalog_digest == payload.snapshot.catalog_digest
        )
    )
    if catalog is None:
        raise LakeOperationUnknown("Governed market-data catalog was not found.")
    _validate_contract(payload.snapshot, catalog)
    existing = db.scalar(
        select(LakeGovernanceSnapshot).where(
            or_(
                LakeGovernanceSnapshot.snapshot_key == payload.snapshot_key,
                LakeGovernanceSnapshot.snapshot_digest == payload.snapshot_digest,
            )
        )
    )
    if existing is not None:
        if existing.snapshot_digest == payload.snapshot_digest:
            return existing
        raise LakeOperationConflict(
            "Lake-governance snapshot key is already registered."
        )
    if payload.supersedes_snapshot_id is not None:
        prior = db.get(LakeGovernanceSnapshot, payload.supersedes_snapshot_id)
        if prior is None:
            raise LakeOperationUnknown(
                "Superseded lake-governance snapshot was not found."
            )
        if payload.snapshot.as_of <= prior.as_of:
            raise LakeOperationConflict(
                "Superseding governance must advance its clock."
            )
    record = LakeGovernanceSnapshot(
        snapshot_key=payload.snapshot_key,
        as_of=payload.snapshot.as_of,
        catalog_digest=payload.snapshot.catalog_digest,
        snapshot=payload.snapshot.model_dump(mode="json"),
        snapshot_digest=payload.snapshot_digest,
        supersedes_snapshot_id=payload.supersedes_snapshot_id,
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    return record


def evaluate_admission(
    db: Session, payload: LakeAdmissionRequest
) -> LakeAdmissionDecision:
    record, contract, catalog = _load_contract(db, payload.snapshot_digest)
    partition = next(
        (
            item
            for item in catalog.partitions
            if item.content_digest == payload.partition_digest
        ),
        None,
    )
    if partition is None:
        raise LakeOperationUnknown("Partition is absent from the governed catalog.")
    slo = next(
        (
            item
            for item in contract.quality_slos
            if item.dataset_key == partition.dataset_key
            and item.layer == partition.layer
        ),
        None,
    )
    if slo is None:
        raise LakeOperationUnknown("No quality SLO governs this partition.")
    reasons: list[str] = []
    freshness = int((payload.evaluated_at - payload.last_available_at).total_seconds())
    if freshness < 0:
        reasons.append("future_availability")
    if freshness > slo.maximum_freshness_seconds:
        reasons.append("stale_data")
    if payload.observed_schema_digest != slo.expected_schema_digest:
        reasons.append("schema_mismatch")
    if payload.duplicate_count > slo.maximum_duplicate_count:
        reasons.append("duplicate_limit_exceeded")
    if payload.gap_count > slo.maximum_gap_count:
        reasons.append("gap_limit_exceeded")
    quality_passed = not reasons
    rules = [
        item
        for item in contract.entitlements
        if item.principal == payload.principal
        and partition.dataset_key in item.dataset_keys
        and payload.action in item.actions
        and item.purpose == payload.purpose
        and item.valid_from <= payload.evaluated_at
        and (item.valid_to is None or payload.evaluated_at < item.valid_to)
    ]
    entitlement_passed = bool(rules)
    if not entitlement_passed:
        reasons.append("entitlement_denied")
    hold = any(
        item.object_digest == partition.content_digest
        and item.active_from <= payload.evaluated_at
        and (item.active_until is None or payload.evaluated_at < item.active_until)
        for item in contract.retention_holds
    )
    if payload.action == "delete" and hold:
        reasons.append("retention_hold")
    budget = next(
        item
        for item in contract.storage_budgets
        if item.dataset_key == partition.dataset_key
    )
    observed = contract.observed_storage_bytes.get(partition.dataset_key, 0)
    if observed >= budget.maximum_bytes:
        storage_state = "exhausted"
        reasons.append("storage_budget_exhausted")
    elif observed * 100 >= budget.maximum_bytes * budget.warning_percent:
        storage_state = "warning"
    else:
        storage_state = "healthy"
    allowed = (
        quality_passed
        and entitlement_passed
        and not (payload.action == "delete" and hold)
        and storage_state != "exhausted"
    )
    detail = {
        "allowed": allowed,
        "action": payload.action,
        "dataset_key": partition.dataset_key,
        "partition_digest": partition.content_digest,
        "purpose": payload.purpose,
        "quality_passed": quality_passed,
        "entitlement_passed": entitlement_passed,
        "retention_hold_active": hold,
        "storage_state": storage_state,
        "reason_codes": sorted(set(reasons)),
    }
    event = _record_event(
        db,
        record,
        "admission_decision",
        partition.content_digest,
        detail,
        payload.principal,
    )
    return LakeAdmissionDecision(
        allowed=allowed,
        reason_codes=detail["reason_codes"],
        dataset_key=partition.dataset_key,
        partition_digest=partition.content_digest,
        quality_passed=quality_passed,
        entitlement_passed=entitlement_passed,
        retention_hold_active=hold,
        storage_state=storage_state,
        event_digest=event.event_digest,
        claim_boundary=(
            "Metadata-only quality, lineage, entitlement, retention and capacity "
            "decision; protected source payload is neither read nor retained."
        ),
    )


def disable_publication(
    db: Session, payload: PublicationActionRequest
) -> PublicationState:
    record, contract, _ = _load_contract(db, payload.snapshot_digest)
    publication = _publication(contract, payload.publication_key)
    event = _record_event(
        db,
        record,
        "publication_disabled",
        publication.publication_key,
        {
            "state": "disabled",
            "reason_code": payload.reason_code,
            "publication_digest": publication.publication_digest,
            "catalog_digest": publication.catalog_digest,
        },
        payload.acted_by,
    )
    return PublicationState(
        publication_key=publication.publication_key,
        state="disabled",
        publication_digest=publication.publication_digest,
        catalog_digest=publication.catalog_digest,
        event_digest=event.event_digest,
    )


def restore_publication(db: Session, payload: RestoreRequest) -> PublicationState:
    record, contract, _ = _load_contract(db, payload.snapshot_digest)
    publication = _publication(contract, payload.publication_key)
    recovery = next(
        (
            item
            for item in contract.recovery_manifests
            if item.recovery_key == payload.recovery_key
        ),
        None,
    )
    if recovery is None:
        raise LakeOperationUnknown("Recovery manifest was not found.")
    if not recovery.integrity_verified:
        raise LakeOperationConflict("Recovery manifest is not integrity verified.")
    if payload.restored_catalog_digest != recovery.catalog_digest:
        raise LakeOperationConflict("Restored catalog digest does not match recovery.")
    if set(payload.restored_object_digests) != set(recovery.object_digests):
        raise LakeOperationConflict(
            "Restored object set does not match recovery manifest."
        )
    prior = db.scalar(
        select(LakeOperationEvent)
        .where(
            LakeOperationEvent.snapshot_id == record.id,
            LakeOperationEvent.subject_key == publication.publication_key,
        )
        .order_by(LakeOperationEvent.recorded_at.desc())
        .limit(1)
    )
    if prior is None or prior.event_type != "publication_disabled":
        raise LakeOperationConflict("Publication must be disabled before restore.")
    event = _record_event(
        db,
        record,
        "publication_restored",
        publication.publication_key,
        {
            "state": "restored",
            "publication_digest": publication.publication_digest,
            "catalog_digest": recovery.catalog_digest,
            "recovery_key": recovery.recovery_key,
            "backup_digest": recovery.backup_digest,
            "restored_object_digests": sorted(payload.restored_object_digests),
        },
        payload.acted_by,
    )
    return PublicationState(
        publication_key=publication.publication_key,
        state="restored",
        publication_digest=publication.publication_digest,
        catalog_digest=recovery.catalog_digest,
        event_digest=event.event_digest,
    )


def lineage_for(contract: LakeGovernanceContract, digest: str) -> list:
    return [
        item
        for item in contract.lineage_edges
        if item.input_digest == digest or item.output_digest == digest
    ]


def _load_contract(db: Session, snapshot_digest: str):
    record = db.scalar(
        select(LakeGovernanceSnapshot).where(
            LakeGovernanceSnapshot.snapshot_digest == snapshot_digest
        )
    )
    if record is None:
        raise LakeOperationUnknown("Lake-governance snapshot was not found.")
    contract = LakeGovernanceContract.model_validate(record.snapshot)
    catalog_record = db.scalar(
        select(MarketDataCatalogSnapshot).where(
            MarketDataCatalogSnapshot.catalog_digest == contract.catalog_digest
        )
    )
    if catalog_record is None:
        raise LakeOperationUnknown("Governed catalog was not found.")
    return (
        record,
        contract,
        ImmutableMarketDataCatalog.model_validate(catalog_record.catalog),
    )


def _validate_contract(
    contract: LakeGovernanceContract, catalog_record: MarketDataCatalogSnapshot
) -> None:
    catalog = ImmutableMarketDataCatalog.model_validate(catalog_record.catalog)
    source_digests = {item.content_digest for item in catalog.partitions}
    known = set(source_digests)
    for edge in contract.lineage_edges:
        if edge.input_digest not in known:
            raise LakeOperationConflict(
                "Lineage input is not a known source or output."
            )
        known.add(edge.output_digest)
    for publication in contract.publications:
        if any(item not in known for item in publication.output_digests):
            raise LakeOperationConflict("Publication output is absent from lineage.")
    for recovery in contract.recovery_manifests:
        if any(item not in source_digests for item in recovery.object_digests):
            raise LakeOperationConflict(
                "Recovery manifest contains an unknown source object."
            )


def _publication(contract: LakeGovernanceContract, key: str):
    publication = next(
        (item for item in contract.publications if item.publication_key == key), None
    )
    if publication is None:
        raise LakeOperationUnknown("Derived publication was not found.")
    return publication


def _record_event(
    db: Session,
    snapshot: LakeGovernanceSnapshot,
    event_type: str,
    subject_key: str,
    detail: dict,
    actor: str,
) -> LakeOperationEvent:
    prior = db.scalar(
        select(LakeOperationEvent)
        .where(LakeOperationEvent.snapshot_id == snapshot.id)
        .order_by(LakeOperationEvent.recorded_at.desc())
        .limit(1)
    )
    previous = prior.event_digest if prior is not None else None
    event_digest = record_digest(
        {
            "snapshot_digest": snapshot.snapshot_digest,
            "event_type": event_type,
            "subject_key": subject_key,
            "detail": detail,
            "previous_event_digest": previous,
            "recorded_by": actor,
        }
    )
    existing = db.scalar(
        select(LakeOperationEvent).where(
            LakeOperationEvent.event_digest == event_digest
        )
    )
    if existing is not None:
        return existing
    event = LakeOperationEvent(
        snapshot_id=snapshot.id,
        event_type=event_type,
        subject_key=subject_key,
        detail=detail,
        previous_event_digest=previous,
        event_digest=event_digest,
        recorded_by=actor,
    )
    db.add(event)
    db.flush()
    return event
