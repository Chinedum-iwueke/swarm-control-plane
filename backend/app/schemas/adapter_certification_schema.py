from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdapterCertificationSchemaCreate(StrictModel):
    name: Literal["venue-adapter-certification-and-demo-parity"]
    version: Literal["1.0.0", "1.1.0"]
    producer: Literal[
        "bt.institutional.adapter_certification.adapter_certification_receipt"
    ]
    source_commit: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    specification_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    specification: dict
    status: Literal["active"] = "active"
    registered_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)


class AdapterCertificationSchemaResponse(StrictModel):
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
