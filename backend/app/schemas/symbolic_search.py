from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ALLOWED_OPERATORS = {
    "field",
    "constant",
    "parameter",
    "lag",
    "rolling_mean",
    "abs",
    "log",
    "negate",
    "add",
    "subtract",
    "multiply",
    "divide",
    "greater",
    "less",
    "and",
    "or",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SymbolicConstraints(StrictModel):
    maximum_candidates: int = Field(ge=1, le=10_000)
    maximum_nodes: int = Field(ge=1, le=1_000)
    maximum_depth: int = Field(ge=1, le=32)
    maximum_constants: int = Field(ge=0, le=100)
    allowed_operators: list[str] = Field(min_length=1, max_length=20)
    required_fields: list[str] = Field(default_factory=list, max_length=100)
    allow_parameters: bool = False

    @model_validator(mode="after")
    def grammar(self):
        if len(self.allowed_operators) != len(set(self.allowed_operators)):
            raise ValueError("allowed operators must be unique")
        if not set(self.allowed_operators).issubset(ALLOWED_OPERATORS):
            raise ValueError("grammar contains an unsupported operator")
        if "field" not in self.allowed_operators:
            raise ValueError("grammar must permit field terminals")
        if len(self.required_fields) != len(set(self.required_fields)):
            raise ValueError("required fields must be unique")
        return self


class SymbolicSearchCreate(StrictModel):
    run_key: str = Field(min_length=3, max_length=180)
    base_factor_program_id: UUID
    prompt_policy_bundle_id: UUID
    constraints: SymbolicConstraints
    generated_by: str = Field(min_length=3, max_length=150)


class GeneratorIdentity(StrictModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    seed: int = Field(ge=0, le=2**63 - 1)
    candidate_index: int = Field(ge=0, le=1_000_000)


class SymbolicCandidateCreate(StrictModel):
    candidate_key: str = Field(min_length=3, max_length=180)
    expression: dict[str, Any]
    output_unit: str = Field(min_length=1, max_length=80)
    generator: GeneratorIdentity
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    submitted_by: str = Field(min_length=3, max_length=150)


class SymbolicSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_key: str
    base_factor_program_id: UUID
    prompt_policy_bundle_id: UUID
    constraints: dict
    constraints_digest: str
    status: str
    candidate_count: int
    accepted_count: int
    closure: dict
    generated_by: str
    created_at: datetime


class SymbolicCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    candidate_key: str
    proposal: dict
    proposal_digest: str
    semantic_digest: str | None
    status: Literal["accepted", "duplicate", "rejected"]
    violations: list[str]
    compiled: dict
    validation_digest: str
    submitted_by: str
    created_at: datetime


class SymbolicSearchQuarantine(StrictModel):
    actor: str = Field(min_length=3, max_length=150)
    reason: str = Field(min_length=10, max_length=1_000)
