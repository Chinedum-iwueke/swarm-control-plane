from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionScheduleSchemaCreate(StrictModel):
    name: Literal["baseline-execution-scheduler"]
    version: Literal["1.0.0"]
    producer: Literal["bt.institutional.execution_scheduler.execution_schedule_receipt"]
    source_commit: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    specification_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    specification: dict
    status: Literal["active"] = "active"
    registered_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class ExecutionScheduleSchemaResponse(StrictModel):
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
