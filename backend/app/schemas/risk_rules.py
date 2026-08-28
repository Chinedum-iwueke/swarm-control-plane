from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarginTier(StrictModel):
    tier: int = Field(ge=1)
    notional_floor: Decimal = Field(ge=0)
    notional_cap: Decimal = Field(gt=0)
    maximum_leverage: Decimal = Field(gt=0)
    maintenance_margin_rate: Decimal = Field(gt=0, lt=1)
    maintenance_amount: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def valid_range(self):
        if self.notional_cap <= self.notional_floor:
            raise ValueError("margin tier cap must exceed floor")
        return self


class VenueRulePack(StrictModel):
    schema_version: Literal["venue-risk-rule-pack-v1.0.0"]
    venue_id: str = Field(pattern=_KEY, max_length=100)
    instrument_id: str = Field(pattern=_KEY, max_length=150)
    listing_id: str = Field(pattern=_KEY, max_length=150)
    version: str = Field(pattern=_KEY, max_length=100)
    source_uri: str = Field(min_length=1, max_length=1000)
    source_digest: str = Field(pattern=_DIGEST)
    observed_at: datetime
    available_at: datetime
    effective_from: datetime
    effective_to: datetime | None = None
    status: Literal["active", "suspended", "retired"]
    transition: Literal["activate", "amend", "suspend", "retire"]
    supersedes_rule_pack_digest: str | None = Field(default=None, pattern=_DIGEST)
    margin_tiers: list[MarginTier] = Field(min_length=1, max_length=100)
    price_increment: Decimal = Field(gt=0)
    quantity_increment: Decimal = Field(gt=0)
    maximum_mark_deviation: Decimal = Field(gt=0, lt=1)
    maximum_abs_funding_rate: Decimal = Field(gt=0, lt=1)
    minimum_liquidation_buffer: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def valid_pack(self):
        clocks = (
            self.observed_at,
            self.available_at,
            self.effective_from,
            self.effective_to,
        )
        if any(value is not None and value.utcoffset() is None for value in clocks):
            raise ValueError("rule clocks must be timezone-aware")
        if self.available_at < self.observed_at:
            raise ValueError("rule availability cannot precede observation")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("rule expiry must follow activation")
        if (
            self.transition == "activate"
            and self.supersedes_rule_pack_digest is not None
        ):
            raise ValueError("initial activation cannot supersede another pack")
        if self.transition != "activate" and self.supersedes_rule_pack_digest is None:
            raise ValueError("rule transition must bind its predecessor")
        tiers = sorted(self.margin_tiers, key=lambda item: item.notional_floor)
        if [item.tier for item in tiers] != list(range(1, len(tiers) + 1)):
            raise ValueError("margin tier identities must be contiguous")
        if tiers[0].notional_floor != 0:
            raise ValueError("margin tiers must begin at zero")
        if any(
            left.notional_cap != right.notional_floor
            for left, right in pairwise(tiers)
        ):
            raise ValueError("margin tiers must be contiguous without gaps")
        return self


class PositionState(StrictModel):
    side: Literal["long", "short"]
    quantity: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    mark_price: Decimal = Field(gt=0)
    index_price: Decimal = Field(gt=0)
    collateral: Decimal = Field(gt=0)
    requested_leverage: Decimal = Field(gt=0)
    accrued_funding: Decimal
    fee_reserve: Decimal = Field(ge=0)
    state_digest: str = Field(pattern=_DIGEST)


class RiskRuleRequest(StrictModel):
    schema_version: Literal["risk-rule-evaluation-request-v1.0.0"]
    reference_snapshot_id: UUID
    reference_snapshot_digest: str = Field(pattern=_DIGEST)
    risk_stress_assessment_id: UUID
    risk_stress_dossier_digest: str = Field(pattern=_DIGEST)
    rule_pack: VenueRulePack
    rule_pack_digest: str = Field(pattern=_DIGEST)
    position: PositionState
    evaluated_at: datetime
    maximum_rule_age_seconds: int = Field(gt=0)
    allocation_authority: Literal[False] = False
    order_authority: Literal[False] = False
    capital_authority: Literal[False] = False

    @model_validator(mode="after")
    def aware_evaluation(self):
        if self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluation clock must be timezone-aware")
        return self


class RiskRuleEvaluationCreate(StrictModel):
    evaluation_key: str = Field(pattern=_KEY, max_length=180)
    request: RiskRuleRequest
    request_digest: str = Field(pattern=_DIGEST)
    evaluated_by: str = Field(pattern=_KEY, max_length=150)


class RiskRuleEvaluationResponse(RiskRuleEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference_snapshot_id: UUID
    risk_stress_assessment_id: UUID
    rule_pack_digest: str
    receipt: dict
    receipt_digest: str
    decision: Literal["allowed", "denied"]
    evaluated_at: datetime
