from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AlertAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acknowledge", "silence", "unsilence"]
    reason: str = Field(min_length=10, max_length=500)
    silence_seconds: int | None = Field(default=None, ge=60, le=86400)

    @model_validator(mode="after")
    def valid_duration(self):
        if self.action == "silence" and self.silence_seconds is None:
            raise ValueError("silence_seconds is required")
        if self.action != "silence" and self.silence_seconds is not None:
            raise ValueError("silence_seconds is valid only for silence")
        return self


class ObservabilityEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: datetime | None = None
