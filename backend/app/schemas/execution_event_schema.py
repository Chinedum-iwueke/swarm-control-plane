from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_DIGEST = r"^[0-9a-f]{64}$"
_COMMIT = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"
_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecutionEventSchemaCreate(StrictModel):
    name: Literal["canonical-execution-event"]
    version: Literal["1.0.0"]
    producer: Literal["bt.institutional.execution.execution_journal_receipt"]
    source_commit: str = Field(pattern=_COMMIT)
    specification_digest: str = Field(pattern=_DIGEST)
    specification: dict
    status: Literal["active"] = "active"
    registered_by: str = Field(pattern=_KEY, max_length=150)


class ExecutionEventSchemaResponse(StrictModel):
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
