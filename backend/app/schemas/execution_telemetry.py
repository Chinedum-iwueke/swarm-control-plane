from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionTelemetrySchemaCreate(StrictModel):
    name: Literal["canonical-venue-telemetry"]
    version: Literal["1.0.0"]
    producer: Literal["bt.institutional.venue_telemetry.venue_telemetry_receipt"]
    source_commit: str = Field(pattern=_COMMIT)
    specification_digest: str = Field(pattern=_DIGEST)
    specification: dict
    status: Literal["active"] = "active"
    registered_by: str = Field(min_length=1, max_length=150)


class ExecutionTelemetrySchemaResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    version: str
    producer: str
    source_commit: str
    specification_digest: str
    specification: dict
    status: str
    registered_by: str
    registered_at: datetime


class ExecutionTelemetryReplayCreate(StrictModel):
    receipt_digest: str = Field(pattern=_DIGEST)
    projection_digest: str = Field(pattern=_DIGEST)
    schema_digest: str = Field(pattern=_DIGEST)
    venue: Literal["binance", "bybit"]
    environment: Literal["shadow", "demo", "live"]
    account_pseudonym: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    status: Literal["current", "stale", "degraded"]
    projection: dict
    registered_by: str = Field(min_length=1, max_length=150)


class ExecutionTelemetryReplayResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    receipt_digest: str
    projection_digest: str
    schema_digest: str
    venue: str
    environment: str
    account_pseudonym: str
    observed_at: datetime
    status: str
    projection: dict
    registered_by: str
    registered_at: datetime


class ExecutionTelemetryOverview(StrictModel):
    generated_at: datetime
    environment: str | None
    venues: list[ExecutionTelemetryReplayResponse]
    counts: dict[str, int]
    claim_boundary: str
