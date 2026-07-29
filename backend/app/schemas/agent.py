from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AgentRuntimeStatus = Literal[
    "idle",
    "busy",
    "degraded",
]


class AgentCreate(BaseModel):
    slug: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    display_name: str = Field(
        min_length=1,
        max_length=200,
    )

    role: str = Field(
        min_length=1,
        max_length=150,
    )

    machine: str = Field(
        min_length=1,
        max_length=100,
    )

    hermes_profile: str = Field(
        min_length=1,
        max_length=150,
    )

    capabilities: list[str] = Field(default_factory=list)

    risk_ceiling: int = Field(
        default=1,
        ge=0,
        le=5,
    )


class AgentHeartbeat(BaseModel):
    status: AgentRuntimeStatus = "idle"

    runtime: str = Field(
        default="hermes",
        min_length=1,
        max_length=100,
    )

    runtime_version: str | None = Field(
        default=None,
        max_length=100,
    )

    capabilities: list[str] | None = None

    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    display_name: str
    role: str
    machine: str
    hermes_profile: str

    runtime: str | None
    runtime_version: str | None

    status: str
    presence: str

    capabilities: list[str]
    heartbeat_metadata: dict
    risk_ceiling: int
    is_enabled: bool

    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CredentialSecretResponse(BaseModel):
    token: str
    token_prefix: str
    created_at: datetime


class AgentRegistrationResponse(BaseModel):
    agent: AgentResponse
    credential: CredentialSecretResponse


class AgentHeartbeatResponse(BaseModel):
    agent_id: uuid.UUID
    status: str
    presence: str
    received_at: datetime


class AgentRevocationResponse(BaseModel):
    agent_id: uuid.UUID
    revoked_credentials: int
    status: str
