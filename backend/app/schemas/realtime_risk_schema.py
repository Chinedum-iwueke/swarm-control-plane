from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RealtimeRiskSchemaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,119}$")
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,49}$")
    producer: Literal["bt.institutional.realtime_risk.realtime_risk_decision_receipt"]
    source_commit: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    specification_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    specification: dict
    status: Literal["active", "inactive"] = "active"
    registered_by: str = Field(min_length=2, max_length=150)


class RealtimeRiskSchemaResponse(RealtimeRiskSchemaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    registered_at: datetime
