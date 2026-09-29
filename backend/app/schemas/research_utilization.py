from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResearchAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_id: str = Field(min_length=8, max_length=100)
    item_id: str = Field(min_length=8, max_length=100)
    item_type: Literal["governed_alpha_assignment", "disc010_signal_screen"]
    priority: int = Field(ge=0, le=1000)
    workers: int = Field(ge=1, le=8)
    locked_by: str = Field(min_length=1, max_length=200)
    locked_at: datetime

    @field_validator("locked_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("locked_at must include a timezone")
        return value


class ResearchSchedulerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str = Field(min_length=1, max_length=255)
    pid: int | None = Field(default=None, ge=1)
    updated_at: datetime | None = None
    configured_worker_ceiling: int = Field(ge=0, le=256)
    resource_worker_budget: int = Field(ge=0, le=256)
    max_concurrent_jobs: int = Field(ge=1, le=16)
    max_workers_per_job: int = Field(ge=1, le=64)
    minimum_free_ram_gib: float = Field(ge=0, le=10_000)
    estimated_worker_ram_gib: float = Field(gt=0, le=10_000)
    available_ram_gib: float = Field(ge=0, le=1_000_000)
    paused_workers: int = Field(ge=0, le=256)
    external_locked_workers: int = Field(ge=0, le=256)

    @field_validator("updated_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("updated_at must include a timezone")
        return value


class ResearchUtilizationSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["research-utilization-snapshot-v1.0.0"]
    sample_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    machine: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    observed_at: datetime
    state: Literal[
        "approved_backtests_running",
        "fallback_research_running",
        "work_queued",
        "resource_blocked",
        "eligible_queue_empty",
    ]
    worker_budget: int = Field(ge=0, le=256)
    active_workers: int = Field(ge=0, le=256)
    queue_counts: dict[Literal["PENDING", "LOCKED", "DONE", "FAILED"], int]
    work_kind_counts: dict[
        Literal["governed_alpha_assignment", "disc010_signal_screen"],
        dict[Literal["PENDING", "LOCKED", "DONE", "FAILED"], int],
    ]
    allocations: list[ResearchAllocation] = Field(max_length=3)
    scheduler: ResearchSchedulerState
    source_commits: dict[Literal["control_plane", "bulletproof"], str]
    latest_completion_at: datetime | None = None
    action_authority: Literal[False]
    capital_or_order_authority: Literal[False]

    @field_validator("observed_at", "latest_completion_at")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must include a timezone")
        return value

    @field_validator("source_commits")
    @classmethod
    def full_source_commits(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit) for commit in value.values()):
            raise ValueError("source commits must be full lowercase Git commits")
        return value

    @model_validator(mode="after")
    def consistent_counts(self):
        statuses = {"PENDING", "LOCKED", "DONE", "FAILED"}
        kinds = {"governed_alpha_assignment", "disc010_signal_screen"}
        if set(self.queue_counts) != statuses:
            raise ValueError("queue_counts must contain every supported status")
        if set(self.work_kind_counts) != kinds or any(
            set(counts) != statuses for counts in self.work_kind_counts.values()
        ):
            raise ValueError("work_kind_counts must contain every kind and status")
        if any(value < 0 for value in self.queue_counts.values()) or any(
            value < 0
            for counts in self.work_kind_counts.values()
            for value in counts.values()
        ):
            raise ValueError("queue counts cannot be negative")
        if set(self.source_commits) != {"control_plane", "bulletproof"}:
            raise ValueError("both source commits are required")
        locked = self.queue_counts.get("LOCKED", 0)
        pending = self.queue_counts.get("PENDING", 0)
        if locked != len(self.allocations):
            raise ValueError("LOCKED count must equal the allocation count")
        if self.active_workers != sum(item.workers for item in self.allocations):
            raise ValueError("active_workers must equal allocated workers")
        if self.active_workers > self.worker_budget:
            raise ValueError("active_workers exceeds the worker budget")
        governed = self.work_kind_counts.get("governed_alpha_assignment", {})
        screens = self.work_kind_counts.get("disc010_signal_screen", {})
        expected = {
            status: governed.get(status, 0) + screens.get(status, 0)
            for status in ("PENDING", "LOCKED", "DONE", "FAILED")
        }
        if any(self.queue_counts.get(status, 0) != count for status, count in expected.items()):
            raise ValueError("queue totals differ from work-kind totals")
        governed_locked = governed.get("LOCKED", 0)
        screen_locked = screens.get("LOCKED", 0)
        if self.state == "approved_backtests_running" and governed_locked == 0:
            raise ValueError("approved_backtests_running requires a locked governed assignment")
        if self.state == "fallback_research_running" and (screen_locked == 0 or governed_locked):
            raise ValueError("fallback_research_running requires only locked signal screens")
        if self.state == "work_queued" and (locked or pending == 0):
            raise ValueError("work_queued requires pending work and no locked work")
        if self.state == "eligible_queue_empty" and (locked or pending):
            raise ValueError("eligible_queue_empty requires no active eligible work")
        return self


class ResearchUtilizationSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    machine: str
    sample_id: str
    observed_at: datetime
    received_at: datetime
    state: str
    worker_budget: int
    active_workers: int
    queue_counts: dict
    work_kind_counts: dict
    allocations: list
    scheduler: dict
    source_commits: dict
    record_digest: str
