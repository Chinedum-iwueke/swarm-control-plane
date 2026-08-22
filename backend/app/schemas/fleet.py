from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FleetMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu_utilization_percent: float = Field(ge=0, le=100)
    load_per_core: float = Field(ge=0, le=1000)
    memory_available_percent: float = Field(ge=0, le=100)
    swap_used_percent: float = Field(ge=0, le=100)
    swap_in_bytes_delta: int = Field(ge=0)
    swap_out_bytes_delta: int = Field(ge=0)
    disk_used_percent: float = Field(ge=0, le=100)
    inode_used_percent: float = Field(ge=0, le=100)
    cpu_pressure_avg10: float = Field(ge=0, le=100)
    io_pressure_avg10: float = Field(ge=0, le=100)
    memory_pressure_avg10: float = Field(ge=0, le=100)
    uptime_seconds: float = Field(ge=0)
    oom_kills_delta: int = Field(ge=0)


class ServiceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    status: Literal["active", "inactive", "failed", "unknown"]


class MachineObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["fleet-observation-v1.0.0"]
    sample_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    machine: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    observed_at: datetime
    metrics: FleetMetrics
    services: list[ServiceHealth] = Field(max_length=30)

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def unique_services(self):
        if len({item.name for item in self.services}) != len(self.services):
            raise ValueError("service names must be unique")
        return self


class MachineObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    machine: str
    sample_id: str
    observed_at: datetime
    received_at: datetime
    metrics: dict
    service_health: dict
    record_digest: str
    retention_class: str


class IncidentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["acknowledge", "silence"]
    reason: str = Field(min_length=10, max_length=500)
    silence_seconds: int | None = Field(default=None, ge=60, le=86400)

    @model_validator(mode="after")
    def validate_silence(self):
        if self.action == "silence" and self.silence_seconds is None:
            raise ValueError("silence_seconds is required for silence")
        if self.action == "acknowledge" and self.silence_seconds is not None:
            raise ValueError("silence_seconds is valid only for silence")
        return self


class FleetIncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    machine: str
    signal: str
    state: str
    severity: str
    generation: int
    summary: str
    evidence: dict
    opened_at: datetime
    updated_at: datetime
    recovered_at: datetime | None
    acknowledged_at: datetime | None
    silenced_until: datetime | None
