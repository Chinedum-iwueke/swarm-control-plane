from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchBudget(StrictModel):
    maximum_evaluations: int = Field(ge=1, le=10_000)
    maximum_batches: int = Field(ge=1, le=10_000)
    batch_size: int = Field(ge=1, le=1_000)

    @model_validator(mode="after")
    def capacity(self):
        if self.maximum_batches * self.batch_size < self.maximum_evaluations:
            raise ValueError("batch capacity must cover maximum_evaluations")
        return self


class SearchObjective(StrictModel):
    metric: str = Field(min_length=1, max_length=100)
    direction: Literal["maximize", "minimize"]


class StatisticalSearchCreate(StrictModel):
    campaign_key: str = Field(min_length=3, max_length=180)
    factor_program_id: UUID
    method: Literal["exhaustive", "structured", "random", "bayesian", "evolutionary"]
    seed: int = Field(ge=0, le=2**63 - 1)
    objective: SearchObjective
    budget: SearchBudget
    exploration_weight: float = Field(default=1.0, gt=0, le=100)
    registered_by: str = Field(min_length=3, max_length=150)


class SearchObservation(StrictModel):
    trial_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["completed", "failed", "cancelled", "invalid"]
    objective_value: float | None = Field(default=None, allow_inf_nan=False)
    result_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def outcome(self):
        if self.status == "completed" and self.objective_value is None:
            raise ValueError("completed observation requires objective_value")
        if self.status != "completed" and self.objective_value is not None:
            raise ValueError("non-result observation cannot carry objective_value")
        return self


class SearchObservationBatch(StrictModel):
    observations: list[SearchObservation] = Field(min_length=1, max_length=1_000)


class SearchCancellation(StrictModel):
    actor: str = Field(min_length=3, max_length=150)
    reason: str = Field(min_length=10, max_length=1_000)


class SearchProposalResponse(BaseModel):
    campaign_id: UUID
    method: str
    batch_number: int
    history_digest: str
    proposals: list[dict]
    budget_remaining: int
    event_digest: str


class StatisticalSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_key: str
    factor_program_id: UUID
    method: str
    specification: dict
    specification_digest: str
    status: str
    proposed_count: int
    observed_count: int
    event_head_digest: str
    registered_by: str
    registered_at: datetime
