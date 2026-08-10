from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z][a-z0-9._-]{0,99}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpusSyncItemCreate(StrictModel):
    source_locator: str = Field(min_length=1, max_length=1000)
    content_digest: str | None = Field(default=None, pattern=_DIGEST)
    classification: dict[str, str] = Field(default_factory=dict)
    access_class: Literal["public", "internal", "restricted", "protected"]
    disposition: Literal[
        "canonical", "quarantined", "duplicate", "superseded", "excluded", "failed"
    ]
    ingestion_job_id: UUID | None = None
    detail: str | None = Field(default=None, max_length=2000)

    @field_validator("source_locator")
    @classmethod
    def locator_is_non_executable_and_relative(cls, value: str) -> str:
        parts = value.split("/")
        if (
            value.startswith("/")
            or "\\" in value
            or ".." in parts
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("source_locator must be a safe logical relative locator")
        return value

    @model_validator(mode="after")
    def evidence_matches_disposition(self):
        if self.disposition in {"canonical", "quarantined"} and (
            self.content_digest is None or self.ingestion_job_id is None
        ):
            raise ValueError(
                "canonical and quarantined items require ingestion evidence"
            )
        if self.disposition == "excluded" and not self.detail:
            raise ValueError("excluded items require a reason")
        return self


class CorpusSyncRunCreate(StrictModel):
    schema_version: Literal["corpus-sync-v1.0.0"]
    project: str = Field(pattern=_NAME)
    source_kind: Literal[
        "founder_inbox",
        "legacy_hermes",
        "imported_prior_result",
        "bulletproof_projection",
    ]
    source_root: str = Field(min_length=1, max_length=500)
    requested_by: str = Field(pattern=_NAME)
    items: list[CorpusSyncItemCreate] = Field(max_length=20_000)


class CorpusSyncItemResponse(CorpusSyncItemCreate):
    id: UUID
    canonical_object_ids: list[UUID]
    predecessor_item_id: UUID | None
    created_at: datetime


class CorpusSyncRunResponse(StrictModel):
    id: UUID
    schema_version: str
    project: str
    source_kind: str
    source_root: str
    inventory_digest: str
    requested_by: str
    status: str
    counts: dict[str, int]
    coverage_digest: str
    items: list[CorpusSyncItemResponse]
    created_at: datetime
