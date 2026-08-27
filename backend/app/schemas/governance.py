import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    reason: str = Field(min_length=1, max_length=2000)
    expires_in_seconds: int = Field(default=3600, ge=60, le=86400)
    authority_exception_id: uuid.UUID | None = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    status: Literal["pending", "approved", "rejected", "revoked", "expired", "consumed"]
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    risk_level: int
    scope: dict
    requested_by: str
    decided_by: str | None
    decision_reason: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    consumed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    approval_id: uuid.UUID
    event_type: str
    actor: str
    reason: str | None
    payload: dict
    created_at: datetime


class ApprovalCenterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    reason: str = Field(min_length=10, max_length=2000)
    expected_review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)
    authority_exception_id: uuid.UUID | None = None


class ApprovalCenterItem(BaseModel):
    approval: ApprovalResponse
    task: dict
    review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    current: bool
    executable: bool
    actionable: bool
    blocked_by: list[dict]
    changed_fields: list[str]
    prerequisites: list[dict]
    mission: dict | None
    authority_policy: dict | None
    notification: dict | None
    notification_duplicates: int
    events: list[ApprovalEventResponse]
    claim_boundary: str


class ApprovalCenterResponse(BaseModel):
    generated_at: datetime
    counts: dict[str, int]
    items: list[ApprovalCenterItem]


class ApprovalCenterDecisionReceipt(BaseModel):
    approval: ApprovalResponse
    action: Literal["approve", "reject"]
    review_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_id: int


class ArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str = Field(min_length=1)
    artifact_type: Literal["log", "report", "result", "evidence"]
    name: str = Field(
        min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
    )
    size_bytes: int = Field(ge=0, le=10_000_000_000)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    location: str = Field(
        min_length=1,
        max_length=2000,
        pattern=r"^(workspace|object)://[A-Za-z0-9][A-Za-z0-9/_.-]*$",
    )
    storage_backend: Literal["workspace", "object"]
    workflow: str = Field(min_length=1, max_length=100)
    workflow_version: str = Field(min_length=1, max_length=50)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    confidentiality: Literal["internal", "confidential", "restricted"] = "internal"
    retention_class: Literal["ephemeral", "standard", "audit", "legal"] = "standard"
    expires_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("location")
    @classmethod
    def safe_location(cls, location: str) -> str:
        path = location.split("://", 1)[1]
        if ".." in path.split("/") or "//" in path:
            raise ValueError("artifact location contains unsafe path segments")
        return location

    @field_validator("metadata")
    @classmethod
    def bounded_metadata(cls, metadata: dict) -> dict:
        if len(json.dumps(metadata, ensure_ascii=True)) > 16_384:
            raise ValueError("artifact metadata exceeds 16 KiB")
        return metadata


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    agent_id: uuid.UUID
    attempt_number: int
    artifact_type: str
    name: str
    size_bytes: int
    sha256: str
    location: str
    storage_backend: str
    workflow: str
    workflow_version: str
    source_commit: str
    confidentiality: str
    retention_class: str
    verification_status: str
    expires_at: datetime | None
    metadata_json: dict
    created_at: datetime
