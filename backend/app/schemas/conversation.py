import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationCreate(StrictModel):
    founder_key: str = Field(
        min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]*$"
    )
    channel: Literal["telegram", "mission-control"]
    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=1, max_length=12000)
    channel_message_id: str | None = Field(default=None, max_length=160)
    reply_to_channel_message_id: str | None = Field(default=None, max_length=160)


class ConversationTurnCreate(StrictModel):
    founder_key: str = Field(
        min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]*$"
    )
    channel: Literal["telegram", "mission-control"]
    message: str = Field(min_length=1, max_length=12000)
    channel_message_id: str | None = Field(default=None, max_length=160)
    reply_to_channel_message_id: str | None = Field(default=None, max_length=160)


class ConversationTransition(StrictModel):
    founder_key: str = Field(
        min_length=3, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9:._-]*$"
    )
    action: Literal["finish", "stop", "resume", "archive"]
    reason: str = Field(min_length=3, max_length=500)


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence: int
    role: str
    channel: str
    channel_message_id: str | None
    reply_to_message_id: uuid.UUID | None
    content: str
    content_digest: str
    detail: dict
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    short_id: str
    founder_key: str
    title: str
    project: str | None
    status: str
    working_summary: str
    current_specification: dict
    specification_digest: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    messages: list[ConversationMessageResponse] = Field(default_factory=list)
    latest_task_id: uuid.UUID | None = None
    latest_task_number: str | None = None


class ConversationTurnResponse(StrictModel):
    conversation: ConversationResponse
    task_id: uuid.UUID
    task_number: str
