from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InfrastructureContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runbook: Literal[
        "vm2-infrastructure",
        "vm2-postgres-deployment",
        "vm2-platform-operations",
    ]
    runbook_version: Literal["1.0.0"]
    operation: Literal[
        "observe-control-plane",
        "restart-control-plane-api",
        "preflight-invariance-postgres",
        "stage-invariance-postgres",
        "start-invariance-postgres-private",
        "initialize-invariance-schema",
        "configure-invariance-backups",
        "verify-invariance-postgres",
        "prepare-invariance-cutover",
        "verify-docker-service",
        "restart-docker-service",
        "verify-redis",
        "verify-storage",
        "verify-certificate",
        "verify-backup",
        "verify-service-health",
    ]
    target: Literal[
        "vm2-control-plane",
        "vm2-invariance-postgres",
        "vm2-production",
    ]
    parameters: dict[str, Any] = Field(default_factory=dict)
    package_name: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    package_version: str | None = Field(
        default=None, pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$"
    )
    package_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def operation_has_no_untyped_parameters(self) -> InfrastructureContract:
        if self.runbook != "vm2-platform-operations" and self.parameters:
            raise ValueError("This operation does not accept parameters.")
        package_values = (
            self.package_name,
            self.package_version,
            self.package_digest,
        )
        if self.runbook == "vm2-platform-operations":
            if not all(package_values):
                raise ValueError("Packaged operations require package attestation.")
            if self.package_name != self.runbook:
                raise ValueError("Package name must match runbook.")
        elif any(package_values):
            raise ValueError("Legacy operations cannot claim a package attestation.")
        return self


class BrokerTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str = Field(min_length=1)


class BrokerTicketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    task_id: uuid.UUID
    task_number: str
    attempt_number: int = Field(ge=1)
    agent_id: uuid.UUID
    machine: Literal["vm2-deployment"]
    task_type: Literal["infrastructure_observation", "infrastructure_operation"]
    risk_level: int = Field(ge=0, le=5)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract: InfrastructureContract
    nonce: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: datetime
    expires_at: datetime

    @field_validator("task_number")
    @classmethod
    def safe_task_number(cls, value: str) -> str:
        if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$", value):
            raise ValueError("task number is unsafe")
        return value

    @model_validator(mode="after")
    def operation_matches_task_type(self) -> BrokerTicketPayload:
        observations = {
            "observe-control-plane",
            "preflight-invariance-postgres",
            "verify-invariance-postgres",
            "prepare-invariance-cutover",
            "verify-docker-service",
            "verify-redis",
            "verify-storage",
            "verify-certificate",
            "verify-backup",
            "verify-service-health",
        }
        expected = (
            "infrastructure_observation"
            if self.contract.operation in observations
            else "infrastructure_operation"
        )
        if self.task_type != expected:
            raise ValueError("operation does not match task type")
        if self.expires_at <= self.issued_at:
            raise ValueError("ticket expiry must follow issuance")
        return self


class BrokerTicketResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: BrokerTicketPayload
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")
