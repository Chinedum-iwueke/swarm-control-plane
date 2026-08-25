import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SAFE = r"^[a-z0-9][a-z0-9_-]*$"


class AgentCharterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["agent-charter-v1.0.0"]
    role: str = Field(min_length=1, max_length=150)
    responsibilities: list[str] = Field(min_length=1, max_length=50)
    capabilities: list[str] = Field(min_length=1, max_length=50)
    allowed_machines: list[str] = Field(min_length=1, max_length=20)
    allowed_task_types: list[str] = Field(min_length=1, max_length=50)
    allowed_repositories: list[str] = Field(default_factory=list, max_length=50)
    risk_ceiling: int = Field(ge=0, le=5)
    accountable_owner: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    conflicts: list[str] = Field(default_factory=list, max_length=50)
    forbidden_actions: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("capabilities", "allowed_machines", "allowed_task_types")
    @classmethod
    def safe_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(__import__("re").fullmatch(SAFE, item) is None for item in values):
            raise ValueError("values must be unique safe names")
        return values


class AgentCharterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    manifest: AgentCharterManifest
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AgentCharterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    agent_id: uuid.UUID
    version: str
    manifest: AgentCharterManifest
    manifest_digest: str
    status: str
    created_by: str
    created_at: datetime
    activated_by: str | None
    activated_at: datetime | None
    supersedes_id: uuid.UUID | None


class AgentCharterActivation(BaseModel):
    activated_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class AgentCapabilityGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: uuid.UUID
    charter_id: uuid.UUID
    capability: str = Field(pattern=SAFE)
    machine: str = Field(pattern=SAFE)
    task_types: list[str] = Field(min_length=1, max_length=50)
    repositories: list[str] = Field(default_factory=list, max_length=50)
    risk_ceiling: int = Field(ge=0, le=5)
    accountable_owner: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    granted_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    reason: str = Field(min_length=1, max_length=500)
    expires_at: datetime

    @model_validator(mode="after")
    def distinct_authority(self):
        if self.granted_by == self.accountable_owner:
            raise ValueError("grantor and accountable owner must be distinct")
        return self


class AgentCapabilityGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    agent_id: uuid.UUID
    charter_id: uuid.UUID
    capability: str
    machine: str
    task_types: list[str]
    repositories: list[str]
    risk_ceiling: int
    accountable_owner: str
    status: str
    granted_by: str
    reason: str
    expires_at: datetime
    revoked_by: str | None
    revoked_at: datetime | None
    revocation_reason: str | None
    record_digest: str
    created_at: datetime


class AgentGrantRevocation(BaseModel):
    revoked_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    reason: str = Field(min_length=1, max_length=500)


class EffectiveAuthorityRequest(BaseModel):
    capability: str = Field(pattern=SAFE)
    machine: str = Field(pattern=SAFE)
    task_type: str = Field(pattern=SAFE)
    repository: str | None = None
    risk_level: int = Field(ge=0, le=5)


class EffectiveAuthorityResponse(BaseModel):
    agent_id: uuid.UUID
    allowed: bool
    reasons: list[str]
    accountable_owner: str | None
    charter_digest: str | None
    package_digest: str | None
    grant_digest: str | None
    snapshot_digest: str
    resolved_at: datetime
