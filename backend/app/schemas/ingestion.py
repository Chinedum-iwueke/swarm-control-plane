from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DIGEST = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z][a-z0-9._-]{0,99}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestionSourceMetadata(StrictModel):
    title: str = Field(min_length=1, max_length=500)
    origin: str = Field(min_length=1, max_length=2000)
    rights: str = Field(min_length=1, max_length=500)
    acquired_at: datetime
    edition_label: str = Field(min_length=1, max_length=300)


class ScientificIngestionCreate(StrictModel):
    schema_version: Literal["scientific-ingestion-v1.0.0"]
    project: str = Field(pattern=_NAME)
    filename: str = Field(min_length=1, max_length=180)
    media_type: Literal["application/pdf", "text/plain", "text/markdown"]
    content_base64: str = Field(min_length=4)
    content_digest: str = Field(pattern=_DIGEST)
    access_class: Literal["public", "internal", "restricted", "protected"]
    source: IngestionSourceMetadata
    requested_by: str = Field(pattern=_NAME)

    @field_validator("content_base64")
    @classmethod
    def content_is_canonical_base64(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("content_base64 is invalid") from exc
        if base64.b64encode(decoded).decode("ascii") != value:
            raise ValueError("content_base64 must use canonical encoding")
        return value

    def content_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


IngestionStatus = Literal[
    "quarantined",
    "scanned",
    "extracted",
    "recovered",
    "validated",
    "published",
    "remediation_required",
    "rejected",
]


class ScientificIngestionResponse(StrictModel):
    id: UUID
    schema_version: str
    project: str
    filename: str
    media_type: str
    content_digest: str
    quarantine_uri: str
    access_class: str
    source: IngestionSourceMetadata
    requested_by: str
    status: IngestionStatus
    stage_report: dict
    published_object_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class IngestionRecoveryCreate(StrictModel):
    schema_version: Literal["scientific-ingestion-recovery-v1.0.0"]
    project: str = Field(pattern=_NAME)
    requested_by: str = Field(pattern=_NAME)
    limit: int = Field(default=100, ge=1, le=500)


class IngestionRecoveryResponse(StrictModel):
    id: UUID
    schema_version: str
    original_job_id: UUID
    sanitized_job_id: UUID | None
    status: Literal[
        "queued", "processing", "recovered", "rejected", "remediation_required"
    ]
    requested_by: str
    receipt: dict
    created_at: datetime
    updated_at: datetime


class IngestionRecoveryBatchResponse(StrictModel):
    queued: int
    existing: int
    recovery_ids: list[UUID]


class CoordinateReplayResponse(StrictModel):
    object_id: UUID
    artifact_id: UUID
    page: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text: str
    replay_digest: str = Field(pattern=_DIGEST)
