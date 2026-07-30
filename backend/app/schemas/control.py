from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ControlScopeType = Literal["global", "machine", "agent"]


class ControlMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: ControlScopeType
    scope_key: str = Field(
        min_length=1,
        max_length=150,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    reason: str = Field(min_length=1, max_length=2000)
    actor: str = Field(
        min_length=1,
        max_length=150,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )


class ControlScopeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope_type: ControlScopeType
    scope_key: str
    is_paused: bool
    reason: str | None
    updated_by: str
    created_at: datetime
    updated_at: datetime


class ControlEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope_type: ControlScopeType
    scope_key: str
    event_type: str
    actor: str
    reason: str | None
    payload: dict
    created_at: datetime


class ControlMutationResponse(BaseModel):
    scope: ControlScopeResponse
    event: ControlEventResponse


class EffectiveControlResponse(BaseModel):
    paused: bool
    reasons: list[str] = Field(default_factory=list)
    matched_scopes: list[ControlScopeResponse] = Field(default_factory=list)
