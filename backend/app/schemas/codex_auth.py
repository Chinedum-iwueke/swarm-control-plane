import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

CodexAuthState = Literal[
    "healthy",
    "authentication_required",
    "awaiting_authorization",
    "expired",
    "error",
]


class CodexAuthRecoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9._-]+$")
    state: CodexAuthState
    generation: int = Field(ge=0)
    verification_uri: HttpUrl | None = None
    device_code: str | None = Field(default=None, min_length=5, max_length=40)
    code_expires_at: datetime | None = None
    failure_summary: str | None = Field(default=None, max_length=500)


class CodexAuthRecoveryRetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=500)


class CodexAuthRecoveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    runtime_key: str
    state: CodexAuthState
    generation: int
    verification_uri: str | None
    device_code: str | None
    code_expires_at: datetime | None
    retry_requested_at: datetime | None
    retry_acknowledged_at: datetime | None
    last_probe_at: datetime | None
    authenticated_at: datetime | None
    failure_summary: str | None
    created_at: datetime
    updated_at: datetime
