from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FounderChannelRequest(StrictModel):
    kind: Literal["task", "mission"]
    project: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    title: str = Field(min_length=3, max_length=160)
    objective: str = Field(min_length=10, max_length=4000)
    risk_level: int = Field(default=0, ge=0, le=5)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)


class FounderChannelDecision(StrictModel):
    reason: str = Field(min_length=10, max_length=1000)
    expires_in_seconds: int = Field(default=900, ge=60, le=3600)
