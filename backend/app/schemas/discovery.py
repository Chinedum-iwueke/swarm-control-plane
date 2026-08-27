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


class Population(StrictModel):
    instruments: list[str] = Field(min_length=1, max_length=500)
    venue_keys: list[str] = Field(min_length=1, max_length=100)
    start_at: datetime
    end_at: datetime
    timeframe: str = Field(pattern=_KEY, max_length=40)
    data_catalog_digest: str = Field(pattern=_DIGEST)
    lake_admission_event_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def valid_interval(self) -> Population:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("population clocks must be timezone aware")
        if self.end_at <= self.start_at:
            raise ValueError("population end must follow start")
        return self


class EffectEstimate(StrictModel):
    metric: str = Field(pattern=_KEY, max_length=100)
    estimate: float
    baseline: float
    incremental_estimate: float
    sample_size: int = Field(ge=1)
    unit: str = Field(pattern=_KEY, max_length=60)


class UncertaintyEstimate(StrictModel):
    method: str = Field(pattern=_KEY, max_length=100)
    lower: float
    upper: float
    confidence_level: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def ordered(self) -> UncertaintyEstimate:
        if self.upper < self.lower:
            raise ValueError("uncertainty interval is reversed")
        return self


class NullControl(StrictModel):
    control_key: str = Field(pattern=_KEY, max_length=120)
    kind: Literal["permutation", "placebo", "negative_control", "time_shift"]
    result: Literal["passed", "failed", "inconclusive"]
    evidence_digest: str = Field(pattern=_DIGEST)


class CostAssessment(StrictModel):
    gross_effect: float
    transaction_cost: float = Field(ge=0)
    financing_cost: float = Field(ge=0)
    impact_cost: float = Field(ge=0)
    net_effect: float
    unit: str = Field(pattern=_KEY, max_length=60)

    @model_validator(mode="after")
    def arithmetic(self) -> CostAssessment:
        expected = (
            self.gross_effect
            - self.transaction_cost
            - self.financing_cost
            - self.impact_cost
        )
        if abs(expected - self.net_effect) > 1e-9:
            raise ValueError("net effect does not reconcile to declared costs")
        return self


class DiscoveryMapDocument(StrictModel):
    schema_version: Literal[1]
    stage: Literal["observation", "anomaly", "mechanism", "opportunity"]
    source_daily_cycle_id: uuid.UUID
    question: str = Field(min_length=10, max_length=1000)
    population: Population
    baseline_definition: str = Field(min_length=5, max_length=2000)
    effect: EffectEstimate
    uncertainty: UncertaintyEstimate
    evidence_object_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    evidence_digests: list[str] = Field(min_length=1, max_length=500)
    regime_controls: list[str] = Field(min_length=1, max_length=100)
    null_controls: list[NullControl] = Field(default_factory=list, max_length=100)
    mechanism: str | None = Field(default=None, min_length=10, max_length=4000)
    rival_explanations: list[str] = Field(default_factory=list, max_length=100)
    falsification_criteria: list[str] = Field(default_factory=list, max_length=100)
    costs: CostAssessment | None = None
    limitations: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def enforce_evidence_ladder(self) -> DiscoveryMapDocument:
        if len(self.evidence_digests) != len(set(self.evidence_digests)):
            raise ValueError("evidence digests must be unique")
        if len(self.evidence_object_ids) != len(self.evidence_digests):
            raise ValueError("evidence IDs and digests must form exact pairs")
        if self.stage in {"anomaly", "mechanism", "opportunity"}:
            if not self.null_controls:
                raise ValueError("anomaly stages require null controls")
            if not any(item.result == "passed" for item in self.null_controls):
                raise ValueError("anomaly stages require a passed null control")
        if self.stage in {"mechanism", "opportunity"} and (
            not self.mechanism
            or not self.rival_explanations
            or not self.falsification_criteria
        ):
            raise ValueError(
                "mechanism stages require mechanism, rivals and falsification"
            )
        if self.stage == "opportunity":
            if self.costs is None:
                raise ValueError("opportunity requires cost assessment")
            if self.costs.net_effect <= 0:
                raise ValueError("cost-erased effects cannot be opportunities")
            if len(self.evidence_object_ids) < 2 or len(self.evidence_digests) < 2:
                raise ValueError(
                    "opportunity requires independent incremental evidence"
                )
            if self.effect.incremental_estimate == 0:
                raise ValueError("opportunity requires a non-zero incremental effect")
        elif self.costs is not None:
            raise ValueError("cost assessment belongs only to opportunity stage")
        return self


class DiscoveryMapCreate(StrictModel):
    map_key: str = Field(pattern=_KEY, max_length=180)
    document: DiscoveryMapDocument
    map_digest: str = Field(pattern=_DIGEST)
    supersedes_map_id: uuid.UUID | None = None
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class DiscoveryMapResponse(DiscoveryMapCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    stage: str
    semantic_fingerprint: str
    status: Literal["active", "superseded"]
    registered_at: datetime


class DiscoveryMapEventResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    map_id: uuid.UUID
    event_type: str
    detail: dict
    previous_event_digest: str | None
    event_digest: str
    recorded_by: str
    recorded_at: datetime
