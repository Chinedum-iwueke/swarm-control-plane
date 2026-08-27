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


class FamilyTrial(StrictModel):
    trial_key: str = Field(pattern=_KEY, max_length=160)
    specification_digest: str = Field(pattern=_DIGEST)
    status: Literal["completed", "failed", "cancelled"]
    primary_metric: float | None = None
    p_value: float | None = Field(default=None, ge=0, le=1)
    sharpe: float | None = None
    sharpe_standard_error: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def completed_has_statistics(self) -> FamilyTrial:
        values = (
            self.primary_metric,
            self.p_value,
            self.sharpe,
            self.sharpe_standard_error,
        )
        if self.status == "completed" and any(value is None for value in values):
            raise ValueError(
                "completed trials require all declared selection statistics"
            )
        if self.status != "completed" and any(value is not None for value in values):
            raise ValueError(
                "failed and cancelled trials cannot carry outcome statistics"
            )
        return self


class ValidationSplit(StrictModel):
    split_key: str = Field(pattern=_KEY, max_length=120)
    winner_rank: int = Field(ge=1)
    candidate_count: int = Field(ge=2)

    @model_validator(mode="after")
    def rank_exists(self) -> ValidationSplit:
        if self.winner_rank > self.candidate_count:
            raise ValueError("winner rank exceeds candidate count")
        return self


class StoppingRecord(StrictModel):
    rule_digest: str = Field(pattern=_DIGEST)
    rule_kind: Literal["fixed_family", "fixed_budget", "sequential"]
    stopped_after_trial: int = Field(ge=1)
    stop_reason: Literal[
        "family_complete", "budget_exhausted", "declared_boundary", "outcome_triggered"
    ]
    outcome_access_before_stop: bool


class SearchFamilyLedger(StrictModel):
    schema_version: Literal[1]
    search_plan_digest: str = Field(pattern=_DIGEST)
    trial_family: str = Field(pattern=_KEY, max_length=180)
    planned_trial_count: int = Field(ge=1, le=100_000)
    trials: list[FamilyTrial] = Field(min_length=1, max_length=100_000)
    reported_winner_trial_key: str = Field(pattern=_KEY, max_length=160)
    stopping: StoppingRecord
    declared_researcher_degrees: list[str] = Field(min_length=1, max_length=200)
    observed_research_operations: list[str] = Field(min_length=1, max_length=500)
    validation_splits: list[ValidationSplit] = Field(min_length=2, max_length=1000)
    finalized_at: datetime

    @model_validator(mode="after")
    def complete_family(self) -> SearchFamilyLedger:
        if self.finalized_at.tzinfo is None:
            raise ValueError("ledger finalization clock must be timezone aware")
        if self.planned_trial_count != len(self.trials):
            raise ValueError("ledger must contain every planned trial")
        keys = [item.trial_key for item in self.trials]
        if len(keys) != len(set(keys)):
            raise ValueError("trial identities must be unique")
        if self.reported_winner_trial_key not in keys:
            raise ValueError("reported winner is absent from the family ledger")
        winner = next(
            item
            for item in self.trials
            if item.trial_key == self.reported_winner_trial_key
        )
        if winner.status != "completed":
            raise ValueError("reported winner must be a completed trial")
        if self.stopping.stopped_after_trial > self.planned_trial_count:
            raise ValueError("stopping position exceeds planned family")
        if len(self.declared_researcher_degrees) != len(
            set(self.declared_researcher_degrees)
        ):
            raise ValueError("declared researcher degrees must be unique")
        return self


class CorrectionPolicy(StrictModel):
    alpha: float = Field(default=0.05, gt=0, lt=1)
    effective_trial_count: int = Field(ge=1)
    maximum_pbo: float = Field(default=0.5, ge=0, le=1)


class SelectionBiasAuditCreate(StrictModel):
    audit_key: str = Field(pattern=_KEY, max_length=180)
    mechanism_evaluation_id: uuid.UUID
    ledger: SearchFamilyLedger
    ledger_digest: str = Field(pattern=_DIGEST)
    correction_policy: CorrectionPolicy
    supersedes_audit_id: uuid.UUID | None = None
    audited_by: str = Field(pattern=_ACTOR, max_length=150)


class SelectionBiasAuditResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    audit_key: str
    mechanism_evaluation_id: uuid.UUID
    ledger: SearchFamilyLedger
    ledger_digest: str
    audit: dict
    conclusion: Literal["blocked", "selection_risk_detected", "selection_adjusted"]
    audit_digest: str
    supersedes_audit_id: uuid.UUID | None
    status: Literal["active", "superseded"]
    audited_by: str
    audited_at: datetime
