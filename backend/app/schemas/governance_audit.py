from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GovernanceAuditExportCreate(StrictModel):
    requested_by: str = Field(min_length=2, max_length=150)


class GovernanceAuditVerifyRequest(StrictModel):
    bundle: dict


class GovernanceAuditExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schema_version: str
    requested_by: str
    event_count: int
    bundle_digest: str
    signature: str
    public_key: str
    key_id: str
    bundle: dict
    created_at: datetime


class GovernanceAuditVerifyResponse(StrictModel):
    valid: bool
    event_count: int
    bundle_digest: str
    key_id: str
    reconstructed: dict
