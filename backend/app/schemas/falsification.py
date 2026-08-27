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


class CompetingExplanation(StrictModel):
    explanation_key: str = Field(pattern=_KEY, max_length=120)
    claim: str = Field(min_length=15, max_length=4000)
    confounders: list[str] = Field(min_length=1, max_length=50)


class DecisiveTest(StrictModel):
    test_key: str = Field(pattern=_KEY, max_length=120)
    prediction: str = Field(min_length=15, max_length=4000)
    null_expectation: str = Field(min_length=15, max_length=4000)
    falsifies_when: str = Field(min_length=15, max_length=4000)
    target_alternatives: list[str] = Field(min_length=1, max_length=50)
    analysis_digest: str = Field(pattern=_DIGEST)

    @model_validator(mode="after")
    def non_tautological(self) -> DecisiveTest:
        normalized = {
            " ".join(value.lower().split())
            for value in (self.prediction, self.null_expectation, self.falsifies_when)
        }
        if len(normalized) != 3:
            raise ValueError("prediction, null and falsification condition must differ")
        return self


class MechanismPlanDocument(StrictModel):
    schema_version: Literal[1]
    mechanism: str = Field(min_length=20, max_length=6000)
    scope: str = Field(min_length=10, max_length=3000)
    assumptions: list[str] = Field(min_length=1, max_length=100)
    alternatives: list[CompetingExplanation] = Field(min_length=1, max_length=100)
    decisive_tests: list[DecisiveTest] = Field(min_length=1, max_length=100)
    dossier_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    opposition_record_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    evidence_cutoff: datetime

    @model_validator(mode="after")
    def closed_plan(self) -> MechanismPlanDocument:
        if self.evidence_cutoff.tzinfo is None:
            raise ValueError("evidence cutoff must be timezone aware")
        keys = [item.explanation_key for item in self.alternatives]
        if len(keys) != len(set(keys)):
            raise ValueError("alternative keys must be unique")
        test_keys = [item.test_key for item in self.decisive_tests]
        if len(test_keys) != len(set(test_keys)):
            raise ValueError("decisive test keys must be unique")
        targets = {
            target
            for item in self.decisive_tests
            for target in item.target_alternatives
        }
        unknown = targets - set(keys)
        if unknown:
            raise ValueError("decisive tests reference unknown alternatives")
        if set(keys) - targets:
            raise ValueError("every competing explanation requires a decisive test")
        return self


class MechanismPlanCreate(StrictModel):
    plan_key: str = Field(pattern=_KEY, max_length=180)
    discovery_map_id: uuid.UUID
    hypothesis_id: uuid.UUID
    plan: MechanismPlanDocument
    plan_digest: str = Field(pattern=_DIGEST)
    registered_by: str = Field(pattern=_ACTOR, max_length=150)


class MechanismPlanResponse(MechanismPlanCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    registered_at: datetime


class TestOutcome(StrictModel):
    test_key: str = Field(pattern=_KEY, max_length=120)
    outcome: Literal["passed", "failed", "inconclusive"]
    observed_result: str = Field(min_length=10, max_length=5000)
    evidence_object_id: uuid.UUID
    evidence_digest: str = Field(pattern=_DIGEST)
    rival_outcomes: dict[str, Literal["ruled_out", "not_ruled_out", "inconclusive"]]


class MechanismEvaluationDocument(StrictModel):
    schema_version: Literal[1]
    plan_digest: str = Field(pattern=_DIGEST)
    outcomes: list[TestOutcome] = Field(min_length=1, max_length=100)
    evaluated_at: datetime
    limitations: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def complete_outcomes(self) -> MechanismEvaluationDocument:
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evaluation clock must be timezone aware")
        keys = [item.test_key for item in self.outcomes]
        if len(keys) != len(set(keys)):
            raise ValueError("test outcomes must be unique")
        return self


class MechanismEvaluationCreate(StrictModel):
    evaluation_key: str = Field(pattern=_KEY, max_length=180)
    plan_id: uuid.UUID
    evaluation: MechanismEvaluationDocument
    evaluation_digest: str = Field(pattern=_DIGEST)
    supersedes_evaluation_id: uuid.UUID | None = None
    evaluated_by: str = Field(pattern=_ACTOR, max_length=150)


class MechanismEvaluationResponse(MechanismEvaluationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conclusion: Literal["supported", "falsified", "unresolved"]
    status: Literal["active", "superseded"]
    evaluated_at: datetime
