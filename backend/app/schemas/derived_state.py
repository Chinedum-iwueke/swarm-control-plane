from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DerivedStateSchedule(StrictModel):
    requested_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,149}$")
    force_full: bool = False


class DerivedStateRunResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    source_epoch_start: int
    source_epoch_target: int
    state: Literal["queued", "running", "succeeded", "needs_attention", "failed"]
    phase: str
    strategy: Literal["no_change", "incremental", "full"]
    requested_by: str
    attempt_count: int
    max_attempts: int
    changed_object_ids: list[str]
    affected_projects: list[str]
    affected_domains: list[str]
    phase_results: dict
    timings_ms: dict
    input_digest: str
    terminal_digest: str | None
    error_summary: str | None
    retryable: bool
    heartbeat_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DerivedStateStatus(StrictModel):
    corpus_epoch: int
    pending_changes: int
    retrieval: dict
    graph: dict
    current: bool
    latest_run: DerivedStateRunResponse | None
    claim_boundary: str


class DerivedStatePhaseReceiptResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    reconciliation_id: UUID
    phase: str
    status: Literal["succeeded"]
    input_digest: str
    output_digest: str
    detail: dict
    started_at: datetime
    completed_at: datetime
