from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldContract(StrictModel):
    unit: str = Field(min_length=1, max_length=80)
    domain: Literal["real", "positive", "nonnegative", "boolean"]
    clock: Literal["decision_open", "decision_close", "event_time"]
    availability_lag: int = Field(ge=0, le=100_000)


class FactorDefinition(StrictModel):
    expression: dict[str, Any]
    output_unit: str = Field(min_length=1, max_length=80)
    missing_policy: Literal["reject", "propagate"] = "reject"


class LabelDefinition(StrictModel):
    field: str
    horizon: int = Field(ge=1, le=100_000)
    kind: Literal["forward_return"] = "forward_return"


class FactorProgramSource(StrictModel):
    schema_version: Literal["factor-experiment-language-v1.0.0"]
    representation_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_clock: Literal["decision_open", "decision_close"]
    fields: dict[str, FieldContract]
    parameters: dict[str, list[int | float | str | bool]] = Field(default_factory=dict)
    factors: dict[str, FactorDefinition]
    label: LabelDefinition
    maximum_trials: int = Field(ge=1, le=10_000)

    @field_validator("fields", "factors")
    @classmethod
    def nonempty(cls, value: dict):
        if not value:
            raise ValueError("mapping cannot be empty")
        return value


class FactorProgramCreate(StrictModel):
    program_key: str = Field(min_length=3, max_length=180)
    hypothesis_id: UUID
    source: FactorProgramSource
    supersedes_program_id: UUID | None = None
    registered_by: str = Field(min_length=3, max_length=150)


class FactorProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_key: str
    hypothesis_id: UUID
    language_version: str
    source: dict
    source_digest: str
    semantic_digest: str
    compiled: dict
    compiled_digest: str
    status: str
    supersedes_program_id: UUID | None
    registered_by: str
