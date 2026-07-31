from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_NAME = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_VERSION = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_DIGEST = r"^[0-9a-f]{64}$"


class ParameterDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["string", "integer", "boolean", "cidr-list"]
    required: bool = True
    secret: bool = False
    minimum: int | None = None
    maximum: int | None = None
    allowed_values: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def constraints_match_type(self) -> ParameterDefinition:
        if self.type != "integer" and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("numeric limits require an integer parameter")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum cannot exceed maximum")
        if self.type != "string" and self.allowed_values:
            raise ValueError("allowed values require a string parameter")
        return self


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    machine: str = Field(pattern=_NAME)
    environment: Literal["rehearsal", "staging", "production"]
    service_class: Literal[
        "platform",
        "docker",
        "redis",
        "postgres",
        "storage",
        "certificate",
        "backup",
        "health",
    ]
    writable_roots: list[str] = Field(default_factory=list, max_length=20)
    private_endpoint: str | None = Field(default=None, max_length=255)
    dns_name: str | None = Field(default=None, max_length=253)


class PreflightContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[str] = Field(min_length=1, max_length=30)
    failure_mode: Literal["block"] = "block"


class RehearsalContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: bool = True
    target_profile: str = Field(pattern=_NAME)
    max_evidence_age_hours: int = Field(ge=1, le=720)
    required_evidence: list[str] = Field(min_length=1, max_length=30)


class RollbackDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str = Field(pattern=_NAME)
    triggers: list[str] = Field(min_length=1, max_length=20)
    timeout_seconds: int = Field(ge=1, le=3600)
    required_evidence: list[str] = Field(min_length=1, max_length=20)


class PackagedOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=_NAME)
    category: Literal[
        "docker", "redis", "postgres", "storage", "certificate", "backup", "health"
    ]
    task_type: Literal["infrastructure_observation", "infrastructure_operation"]
    target_profile: str = Field(pattern=_NAME)
    risk_level: int = Field(ge=0, le=5)
    approval_required: bool
    parameters: dict[str, ParameterDefinition] = Field(default_factory=dict)
    preflight: PreflightContract
    evidence: list[str] = Field(min_length=1, max_length=30)
    rollback: RollbackDefinition | None = None

    @model_validator(mode="after")
    def mutation_has_rollback(self) -> PackagedOperation:
        if self.task_type == "infrastructure_operation" and (
            not self.approval_required or self.rollback is None
        ):
            raise ValueError("mutating operations require approval and rollback")
        return self


class RunbookPackageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    name: str = Field(pattern=_NAME)
    version: str = Field(pattern=_VERSION)
    description: str = Field(min_length=1, max_length=300)
    target_profiles: list[TargetProfile] = Field(min_length=1, max_length=20)
    rehearsal: RehearsalContract
    operations: list[PackagedOperation] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def references_exist(self) -> RunbookPackageManifest:
        targets = {profile.name for profile in self.target_profiles}
        if len(targets) != len(self.target_profiles):
            raise ValueError("target profiles must be unique")
        if self.rehearsal.target_profile not in targets:
            raise ValueError("rehearsal target is undefined")
        names = {operation.name for operation in self.operations}
        if len(names) != len(self.operations):
            raise ValueError("operations must be unique")
        if any(operation.target_profile not in targets for operation in self.operations):
            raise ValueError("operation target is undefined")
        return self


class RunbookPackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: RunbookPackageManifest
    manifest_digest: str = Field(pattern=_DIGEST)
    signature: str = Field(min_length=64, max_length=128)
    source_repository: str = Field(pattern=_NAME)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RunbookPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: str
    manifest: RunbookPackageManifest
    manifest_digest: str
    signature: str
    source_repository: str
    source_commit: str
    created_by: str
    created_at: datetime


class RunbookPromotionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["draft", "rehearsed", "approved", "deployed"]
    evidence_digest: str | None = Field(default=None, pattern=_DIGEST)
    approval_reference: str | None = Field(default=None, min_length=1, max_length=150)
    recorded_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RunbookPromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    package_id: uuid.UUID
    state: str
    evidence_digest: str | None
    approval_reference: str | None
    previous_record_digest: str | None
    record_digest: str
    recorded_by: str
    recorded_at: datetime


class RunbookPackageDetail(BaseModel):
    package: RunbookPackageResponse
    promotions: list[RunbookPromotionResponse]


class RunbookOperationResolution(BaseModel):
    package_id: uuid.UUID
    package_name: str
    package_version: str
    manifest_digest: str
    promotion_state: Literal["approved", "deployed"]
    operation: dict[str, Any]
