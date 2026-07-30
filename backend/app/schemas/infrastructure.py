from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InfrastructureContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runbook: Literal["vm2-infrastructure", "vm2-postgres-deployment"]
    runbook_version: Literal["1.0.0"]
    operation: Literal[
        "observe-control-plane",
        "restart-control-plane-api",
        "preflight-invariance-postgres",
    ]
    target: Literal["vm2-control-plane", "vm2-invariance-postgres"]
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def operation_has_no_untyped_parameters(self) -> InfrastructureContract:
        if self.parameters:
            raise ValueError("This operation does not accept parameters.")
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
    risk_level: int = Field(ge=0, le=3)
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
        expected = (
            "infrastructure_operation"
            if self.contract.operation == "restart-control-plane-api"
            else "infrastructure_observation"
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
