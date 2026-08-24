from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_KEY = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DailyResearchQuestion(StrictModel):
    question_key: str = Field(pattern=_KEY, max_length=150)
    question: str = Field(min_length=10, max_length=2000)
    rationale: str = Field(min_length=10, max_length=4000)
    source: Literal["founder_priority", "portfolio_gap", "literature", "prior_failure"]
    tags: list[str] = Field(default_factory=list, max_length=20)


class DailyResearchSchedule(StrictModel):
    weekdays_utc: list[int] = Field(min_length=1, max_length=7)
    hour_utc: int = Field(ge=0, le=23)

    @model_validator(mode="after")
    def weekdays_are_unique(self) -> "DailyResearchSchedule":
        if any(day < 0 or day > 6 for day in self.weekdays_utc):
            raise ValueError("weekdays must be between 0 and 6")
        if len(set(self.weekdays_utc)) != len(self.weekdays_utc):
            raise ValueError("weekdays must be unique")
        return self


class DailyResearchBudget(StrictModel):
    max_cycles_per_week: int = Field(ge=1, le=7)
    max_trials_per_cycle: int = Field(default=1, ge=1, le=3)
    max_compute_seconds_per_cycle: int = Field(ge=60, le=14400)


class ResearchProgramCreate(StrictModel):
    program_key: str = Field(pattern=_KEY, max_length=150)
    title: str = Field(min_length=1, max_length=300)
    mandate: list[DailyResearchQuestion] = Field(min_length=1, max_length=100)
    schedule: DailyResearchSchedule
    budget: DailyResearchBudget
    active: bool = True
    created_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=150)

    @model_validator(mode="after")
    def question_keys_are_unique(self) -> "ResearchProgramCreate":
        keys = [item.question_key for item in self.mandate]
        if len(keys) != len(set(keys)):
            raise ValueError("question keys must be unique")
        return self


class ResearchProgramResponse(ResearchProgramCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime


class ResearchDailyCycleResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    program_id: UUID
    cycle_date: date
    question_key: str
    question: str
    question_digest: str
    status: Literal[
        "awaiting_brief",
        "duplicate_avoided",
        "registered",
        "running",
        "completed",
        "attention_required",
    ]
    budget: dict
    duplicate_hypothesis_id: UUID | None
    hypothesis_id: UUID | None
    task_id: UUID | None
    digest: dict
    created_at: datetime
    completed_at: datetime | None


class ResearchCycleLink(StrictModel):
    hypothesis_id: UUID
    task_id: UUID


class ResearchCycleApproval(StrictModel):
    expected_question_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected"]
    rationale: str = Field(min_length=10, max_length=4000)
    decided_by: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=150)


class ResearchCycleEventResponse(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    cycle_id: UUID
    sequence: int
    event_type: Literal["proposal_created", "approved", "rejected", "task_ready"]
    detail: dict
    record_digest: str
    created_at: datetime


class DailyResearchDigest(StrictModel):
    date: date
    cycles: list[ResearchDailyCycleResponse]
    learned: list[str]
    rejected: list[str]
    uncertain: list[str]
    next_questions: list[str]


class WeeklyResearchMetrics(StrictModel):
    week_start: date
    cycle_count: int
    completed_count: int
    duplicate_work_avoided: int
    negative_results_retained: int
    reproduction_rate: float
    trial_adjusted_survivor_rate: float
    median_seconds_to_registered_experiment: float | None
    terminal_babysitting_events: int
