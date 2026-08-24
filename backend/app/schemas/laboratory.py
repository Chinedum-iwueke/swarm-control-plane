from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Sha256 = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LaboratoryPublicationCreate(StrictModel):
    schema_version: Literal["laboratory-publication-v1.0.0"]
    trial_id: UUID
    result_id: UUID
    run_object_id: UUID
    repository_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    dataset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_model_bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    representation_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProjectionReceiptCreate(StrictModel):
    schema_version: Literal["laboratory-projection-receipt-v1.0.0"]
    graph_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    graph_source_epoch: int = Field(ge=0)
    retrieval_corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_source_epoch: int = Field(ge=0)


class MemoryReceiptCreate(StrictModel):
    schema_version: Literal["bulletproof-memory-publication-receipt-v1.0.0"]
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    memory_database_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_key: str = Field(min_length=1, max_length=200)
    disposition: Literal["created", "existing"]


class PublicationFailureCreate(StrictModel):
    stage: Literal["projection", "memory"]
    category: str = Field(min_length=1, max_length=100)
    detail: str = Field(min_length=1, max_length=2000)
    retryable: bool


class LaboratoryPublicationEventResponse(StrictModel):
    sequence: int
    event_type: str
    detail: dict
    record_digest: str
    created_at: datetime


class LaboratoryPublicationResponse(StrictModel):
    id: UUID
    trial_id: UUID
    result_id: UUID
    run_object_id: UUID
    request_digest: str
    bundle_digest: str
    state: str
    lineage: dict
    canonical_receipt: dict
    projection_receipt: dict
    memory_receipt: dict
    failure: dict
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class LaboratoryReplayResponse(LaboratoryPublicationResponse):
    events: list[LaboratoryPublicationEventResponse]
