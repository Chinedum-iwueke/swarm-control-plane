from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ServiceInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    kind: Literal["http", "event", "database", "socket", "filesystem", "process"]


class ServiceDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    required: bool = True


class ServiceCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    display_name: str = Field(min_length=2, max_length=160)
    owner: str = Field(min_length=2, max_length=100)
    recovery_owner: str = Field(min_length=2, max_length=100)
    runtime_kind: Literal["docker", "systemd", "launchd", "external"]
    intended_machines: list[str] = Field(min_length=1, max_length=20)
    interfaces: list[ServiceInterface] = Field(default_factory=list, max_length=30)
    dependencies: list[ServiceDependency] = Field(default_factory=list, max_length=30)
    data_classes: list[str] = Field(min_length=1, max_length=20)
    slo: dict = Field(min_length=1)
    recovery_plan: dict = Field(min_length=1)

    @model_validator(mode="after")
    def unique_contracts(self):
        if len(set(self.intended_machines)) != len(self.intended_machines):
            raise ValueError("intended machines must be unique")
        if len({item.name for item in self.interfaces}) != len(self.interfaces):
            raise ValueError("interface names must be unique")
        if self.service_key in {item.service_key for item in self.dependencies}:
            raise ValueError("service cannot depend on itself")
        return self


class ServiceCatalogCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["service-catalog-v1.0.0"]
    catalog_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_repository: str = Field(min_length=2, max_length=200)
    source_commit: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    entries: list[ServiceCatalogEntry] = Field(min_length=1, max_length=500)

    @field_validator("entries")
    @classmethod
    def unique_and_closed(cls, entries):
        keys = [item.service_key for item in entries]
        if len(keys) != len(set(keys)):
            raise ValueError("service keys must be unique")
        unknown = sorted(
            {d.service_key for item in entries for d in item.dependencies} - set(keys)
        )
        if unknown:
            raise ValueError(
                f"dependencies are absent from catalog: {', '.join(unknown)}"
            )
        return entries


class ServiceCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    catalog_version: str
    manifest_digest: str
    manifest: dict
    source_repository: str
    source_commit: str
    created_by: str
    created_at: datetime


class CatalogActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=10, max_length=500)


class ServiceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service_key: str
    machine: str
    runtime_kind: Literal["docker", "systemd", "launchd", "external"]
    status: Literal["healthy", "degraded", "unhealthy", "missing"]
    observed_at: datetime
    interfaces: dict[str, str] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[ServiceObservation] = Field(max_length=2000)
    freshness_seconds: int = Field(default=300, ge=30, le=86400)
    observed_at: datetime | None = None
