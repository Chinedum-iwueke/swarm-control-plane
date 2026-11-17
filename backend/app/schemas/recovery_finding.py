"""Evidence-bound obligations, not model-issued recovery authority."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecoveryFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["recovery-finding-v1"] = "recovery-finding-v1"
    subject_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirement_ref: str = Field(min_length=1, max_length=200)
    finding: str = Field(min_length=1, max_length=16000)
    owning_stage: Literal["method_design", "data_admission", "engineering", "execution", "authority", "triage"]
    severity: Literal["blocker", "warning"] = "blocker"
    classification_status: Literal["requires_diagnosis", "deterministically_classified"]
    allowed_changes: list[str] = Field(min_length=1, max_length=8)
    verification: list[str] = Field(min_length=1, max_length=8)
    recovery_condition: str = Field(min_length=1, max_length=2000)
    scientific_approval: Literal[False] = False
    execution_authority: Literal[False] = False
