from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

_DIGEST = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z][a-z0-9._-]{0,99}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SurveillanceSourceCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    source_key: str = Field(pattern=_NAME)
    name: str = Field(min_length=1, max_length=300)
    feed_url: HttpUrl
    feed_kind: Literal["atom", "rss"]
    domains: list[
        Literal[
            "finance",
            "economics",
            "statistics",
            "machine-learning",
            "market-microstructure",
            "execution",
            "portfolio",
            "risk",
            "trading",
        ]
    ] = Field(min_length=1, max_length=9)
    rights: str = Field(min_length=1, max_length=500)
    access_class: Literal["public", "internal", "restricted", "protected"]
    cadence: Literal["daily", "weekly"]
    freshness_hours: int = Field(ge=1, le=744)
    owner: str = Field(pattern=_NAME)
    allowed_hosts: list[str] = Field(min_length=1, max_length=10)
    is_enabled: bool = True

    @model_validator(mode="after")
    def feed_host_is_allowlisted(self) -> SurveillanceSourceCreate:
        if self.feed_url.host not in self.allowed_hosts:
            raise ValueError("feed host must be explicitly allowlisted")
        return self


class SurveillanceSourceResponse(SurveillanceSourceCreate):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    created_at: datetime


class FeedEntry(StrictModel):
    external_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=1000)
    abstract: str = Field(min_length=1, max_length=50_000)
    canonical_url: HttpUrl
    published_at: datetime
    updated_at: datetime | None = None
    doi: str | None = Field(default=None, max_length=300)
    authors: list[str] = Field(default_factory=list, max_length=100)
    status: Literal["published", "corrected", "retracted"] = "published"
    corrects_external_id: str | None = Field(default=None, max_length=500)
    retracts_external_id: str | None = Field(default=None, max_length=500)


class SourcePollCreate(StrictModel):
    requested_by: str = Field(pattern=_NAME)
    entries: list[FeedEntry] = Field(default_factory=list, max_length=500)
    connector_version: str = Field(min_length=1, max_length=100)
    fetched_at: datetime
    http_status: int = Field(ge=100, le=599)


class FetchReceiptResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    source_id: UUID
    requested_by: str
    connector_version: str
    fetched_at: datetime
    http_status: int
    status: Literal["succeeded", "failed"]
    entry_count: int
    new_count: int
    duplicate_count: int
    rejected_count: int
    receipt_digest: str = Field(pattern=_DIGEST)
    error_code: str | None


class SurveillancePublicationResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    project: str
    source_id: UUID
    external_id: str
    title: str
    canonical_url: str
    published_at: datetime
    publication_status: Literal["published", "corrected", "retracted"]
    content_digest: str = Field(pattern=_DIGEST)
    provenance: dict
    assessment: dict
    routing: dict
    supersedes_id: UUID | None
    created_at: datetime


class WeeklyDigestCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    week_ending: datetime
    requested_by: str = Field(pattern=_NAME)


class WeeklyDigestResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    project: str
    week_ending: datetime
    candidate_count: int
    correction_count: int
    retraction_count: int
    digest: dict
    digest_sha256: str = Field(pattern=_DIGEST)
    created_by: str
    created_at: datetime


class CandidateDispositionCreate(StrictModel):
    decision: Literal["propose_question", "monitor", "dismiss"]
    decided_by: str = Field(pattern=_NAME)
    rationale: str = Field(min_length=1, max_length=2000)


class CandidateDispositionResponse(StrictModel):
    event_id: UUID
    event_digest: str = Field(pattern=_DIGEST)
    publication_id: UUID
    decision: Literal["propose_question", "monitor", "dismiss"]
    approval_required: Literal[True] = True
    proposal: dict
