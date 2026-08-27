from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_DIGEST = r"^[0-9a-f]{64}$"
_ACTOR = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QualitySLO(StrictModel):
    dataset_key: str = Field(pattern=_KEY, max_length=150)
    layer: Literal["raw", "curated"]
    maximum_freshness_seconds: int = Field(ge=1, le=31_536_000)
    maximum_duplicate_count: int = Field(ge=0, le=1_000_000_000)
    maximum_gap_count: int = Field(ge=0, le=1_000_000_000)
    expected_schema_digest: str = Field(pattern=_DIGEST)


class LineageEdge(StrictModel):
    edge_id: str = Field(pattern=_KEY, max_length=200)
    input_digest: str = Field(pattern=_DIGEST)
    output_digest: str = Field(pattern=_DIGEST)
    transformation_digest: str = Field(pattern=_DIGEST)
    transformation_name: str = Field(pattern=_KEY, max_length=150)

    @model_validator(mode="after")
    def no_self_loop(self) -> LineageEdge:
        if self.input_digest == self.output_digest:
            raise ValueError("lineage cannot contain a self-loop")
        return self


class EntitlementRule(StrictModel):
    rule_id: str = Field(pattern=_KEY, max_length=150)
    principal: str = Field(pattern=_ACTOR, max_length=150)
    dataset_keys: list[str] = Field(min_length=1, max_length=200)
    actions: list[Literal["read", "delete"]] = Field(min_length=1, max_length=2)
    purpose: str = Field(pattern=_KEY, max_length=150)
    valid_from: datetime
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def interval_is_valid(self) -> EntitlementRule:
        _aware(self.valid_from)
        if self.valid_to is not None:
            _aware(self.valid_to)
            if self.valid_to <= self.valid_from:
                raise ValueError("entitlement valid_to must follow valid_from")
        return self


class StorageBudget(StrictModel):
    budget_key: str = Field(pattern=_KEY, max_length=150)
    dataset_key: str = Field(pattern=_KEY, max_length=150)
    maximum_bytes: int = Field(ge=1)
    warning_percent: int = Field(ge=1, le=100)


class RetentionHold(StrictModel):
    hold_id: str = Field(pattern=_KEY, max_length=150)
    object_digest: str = Field(pattern=_DIGEST)
    reason_code: str = Field(pattern=_KEY, max_length=150)
    active_from: datetime
    active_until: datetime | None = None

    @model_validator(mode="after")
    def interval_is_valid(self) -> RetentionHold:
        _aware(self.active_from)
        if self.active_until is not None:
            _aware(self.active_until)
            if self.active_until <= self.active_from:
                raise ValueError("retention hold end must follow start")
        return self


class RecoveryManifest(StrictModel):
    recovery_key: str = Field(pattern=_KEY, max_length=150)
    backup_digest: str = Field(pattern=_DIGEST)
    catalog_digest: str = Field(pattern=_DIGEST)
    object_digests: list[str] = Field(min_length=1, max_length=50_000)
    created_at: datetime
    integrity_verified: bool
    verifier: str = Field(pattern=_ACTOR, max_length=150)

    @model_validator(mode="after")
    def clock_is_aware(self) -> RecoveryManifest:
        _aware(self.created_at)
        return self


class DerivedPublication(StrictModel):
    publication_key: str = Field(pattern=_KEY, max_length=150)
    publication_digest: str = Field(pattern=_DIGEST)
    catalog_digest: str = Field(pattern=_DIGEST)
    output_digests: list[str] = Field(min_length=1, max_length=10_000)


class LakeGovernanceContract(StrictModel):
    schema_version: Literal[1]
    as_of: datetime
    catalog_digest: str = Field(pattern=_DIGEST)
    quality_slos: list[QualitySLO] = Field(min_length=1, max_length=1000)
    lineage_edges: list[LineageEdge] = Field(default_factory=list, max_length=50_000)
    entitlements: list[EntitlementRule] = Field(min_length=1, max_length=10_000)
    storage_budgets: list[StorageBudget] = Field(min_length=1, max_length=1000)
    observed_storage_bytes: dict[str, int] = Field(default_factory=dict)
    retention_holds: list[RetentionHold] = Field(
        default_factory=list, max_length=10_000
    )
    recovery_manifests: list[RecoveryManifest] = Field(min_length=1, max_length=1000)
    publications: list[DerivedPublication] = Field(
        default_factory=list, max_length=10_000
    )

    @model_validator(mode="after")
    def contract_is_closed(self) -> LakeGovernanceContract:
        _aware(self.as_of)
        _unique(
            [(item.dataset_key, item.layer) for item in self.quality_slos],
            "quality SLOs",
        )
        _unique([item.edge_id for item in self.lineage_edges], "lineage edges")
        _unique([item.rule_id for item in self.entitlements], "entitlement rules")
        _unique([item.budget_key for item in self.storage_budgets], "storage budgets")
        _unique([item.hold_id for item in self.retention_holds], "retention holds")
        _unique(
            [item.recovery_key for item in self.recovery_manifests],
            "recovery manifests",
        )
        _unique([item.publication_key for item in self.publications], "publications")
        budgets = {item.dataset_key for item in self.storage_budgets}
        if any(key not in budgets for key in self.observed_storage_bytes):
            raise ValueError("observed storage requires a declared dataset budget")
        if any(value < 0 for value in self.observed_storage_bytes.values()):
            raise ValueError("observed storage cannot be negative")
        if any(
            item.catalog_digest != self.catalog_digest
            for item in self.recovery_manifests
        ):
            raise ValueError("recovery manifests must bind the governed catalog")
        if any(
            item.catalog_digest != self.catalog_digest for item in self.publications
        ):
            raise ValueError("publications must bind the governed catalog")
        return self


class LakeGovernanceCreate(StrictModel):
    snapshot_key: str = Field(pattern=_KEY, max_length=150)
    snapshot: LakeGovernanceContract
    snapshot_digest: str = Field(pattern=_DIGEST)
    supersedes_snapshot_id: uuid.UUID | None = None
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class LakeGovernanceResponse(LakeGovernanceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    as_of: datetime
    catalog_digest: str
    registered_at: datetime


class LakeAdmissionRequest(StrictModel):
    snapshot_digest: str = Field(pattern=_DIGEST)
    partition_digest: str = Field(pattern=_DIGEST)
    principal: str = Field(pattern=_ACTOR, max_length=150)
    action: Literal["read", "delete"]
    purpose: str = Field(pattern=_KEY, max_length=150)
    evaluated_at: datetime
    observed_schema_digest: str = Field(pattern=_DIGEST)
    duplicate_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    last_available_at: datetime

    @model_validator(mode="after")
    def clocks_are_aware(self) -> LakeAdmissionRequest:
        _aware(self.evaluated_at)
        _aware(self.last_available_at)
        return self


class LakeAdmissionDecision(StrictModel):
    allowed: bool
    reason_codes: list[str]
    dataset_key: str
    partition_digest: str
    quality_passed: bool
    entitlement_passed: bool
    retention_hold_active: bool
    storage_state: Literal["healthy", "warning", "exhausted"]
    event_digest: str
    claim_boundary: str


class PublicationActionRequest(StrictModel):
    snapshot_digest: str = Field(pattern=_DIGEST)
    publication_key: str = Field(pattern=_KEY, max_length=150)
    acted_by: str = Field(pattern=_ACTOR, max_length=150)
    reason_code: str = Field(pattern=_KEY, max_length=150)


class RestoreRequest(StrictModel):
    snapshot_digest: str = Field(pattern=_DIGEST)
    publication_key: str = Field(pattern=_KEY, max_length=150)
    recovery_key: str = Field(pattern=_KEY, max_length=150)
    restored_catalog_digest: str = Field(pattern=_DIGEST)
    restored_object_digests: list[str] = Field(min_length=1, max_length=50_000)
    acted_by: str = Field(pattern=_ACTOR, max_length=150)


class PublicationState(StrictModel):
    publication_key: str
    state: Literal["active", "disabled", "restored"]
    publication_digest: str
    catalog_digest: str
    event_digest: str


class LakeEventResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    snapshot_id: uuid.UUID
    event_type: str
    subject_key: str
    detail: dict
    previous_event_digest: str | None
    event_digest: str
    recorded_by: str
    recorded_at: datetime


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("lake-operation clocks must be timezone aware")


def _unique(values: list, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")
