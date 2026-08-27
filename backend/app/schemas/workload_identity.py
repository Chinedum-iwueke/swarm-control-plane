from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkloadIdentityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    charter_id: UUID
    package_id: UUID
    version: str = Field(min_length=1, max_length=50)
    audience: str = Field(min_length=1, max_length=150)
    scopes: list[str] = Field(min_length=1)
    accountable_owner: str = Field(min_length=1, max_length=150)
    expires_at: datetime
    created_by: str = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def validate_scopes(self):
        if len(self.scopes) != len(set(self.scopes)) or any(
            "*" in item for item in self.scopes
        ):
            raise ValueError("Scopes must be unique and wildcard-free.")
        return self


class WorkloadIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    agent_id: UUID
    charter_id: UUID
    package_id: UUID
    version: str
    machine: str
    audience: str
    scopes: list[str]
    accountable_owner: str
    manifest_digest: str
    status: str
    valid_from: datetime
    expires_at: datetime
    created_by: str
    created_at: datetime


class WorkloadEnforcementActivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activated_by: str = Field(min_length=1, max_length=150)


class WorkloadEnforcementResponse(BaseModel):
    enforcement_active: bool
    policy_version: str
    policy_digest: str
    covered_credentials: int
    uncovered_credentials: int


class WorkloadCredentialBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=150)


class WorkloadAuthorizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: UUID
    credential_prefix: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1, max_length=150)
    required_scope: str = Field(min_length=1, max_length=100)
    context: dict = Field(default_factory=dict)


class WorkloadAuthorizationResponse(BaseModel):
    id: UUID
    allowed: bool
    reason: str
    receipt_digest: str


class WorkloadSecretPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: UUID
    logical_name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]+$")
    version: str
    required_scope: str
    reference: str = Field(pattern=r"^(file|env|vault)://")
    rotation_due_at: datetime
    expires_at: datetime
    created_by: str

    @model_validator(mode="after")
    def validate_dates(self):
        if self.rotation_due_at >= self.expires_at:
            raise ValueError("Rotation must be due before expiry.")
        return self


class WorkloadEmergencyGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity_id: UUID
    scopes: list[str] = Field(min_length=1)
    reason: str = Field(min_length=10, max_length=500)
    approved_by: str
    independent_reviewer: str
    approval_reference: str
    expires_at: datetime

    @model_validator(mode="after")
    def validate_review(self):
        if self.approved_by == self.independent_reviewer:
            raise ValueError(
                "Emergency approval and independent review must be distinct."
            )
        return self


class WorkloadCredentialRotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str
    overlap_seconds: int = Field(default=300, ge=30, le=900)


class WorkloadLifecycleAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=5, max_length=500)


class WorkloadCredentialRotationResponse(BaseModel):
    identity_id: UUID
    credential_id: UUID
    token: str
    token_prefix: str
    expires_at: datetime
    prior_credential_id: UUID
    overlap_expires_at: datetime


class WorkloadLifecycleOverview(BaseModel):
    enforcement_active: bool
    identities: list[WorkloadIdentityResponse]
    active_secret_policies: int
    active_emergency_grants: int
    expiring_credentials: int
