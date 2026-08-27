from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContextSource(StrictModel):
    object_id: UUID
    selection_reason: str = Field(min_length=3, max_length=500)
    prompt_position: int = Field(ge=0, le=63)


class AgentContextCreate(StrictModel):
    task_id: UUID
    agent_id: UUID
    attempt_number: int = Field(ge=1)
    purpose: str = Field(min_length=3, max_length=1000)
    sources: list[ContextSource] = Field(min_length=1, max_length=32)
    expires_at: datetime
    created_by: str = Field(pattern=r"^[a-z][a-z0-9._-]{0,99}$")
    max_bytes: int = Field(default=65536, ge=1024, le=262144)

    @model_validator(mode="after")
    def positions_are_exact(self):
        positions = sorted(item.prompt_position for item in self.sources)
        if positions != list(range(len(self.sources))):
            raise ValueError("prompt positions must be unique and contiguous from zero")
        if len({item.object_id for item in self.sources}) != len(self.sources):
            raise ValueError("context sources must be unique")
        return self


class ContextItem(StrictModel):
    object_id: UUID
    object_type: str
    content_digest: str
    access_class: str
    selection_reason: str
    sensitivity: str
    expires_at: datetime
    prompt_position: int
    excerpt: str
    citation: dict


class AgentContextResponse(StrictModel):
    id: UUID
    task_id: UUID
    agent_id: UUID
    attempt_number: int
    schema_version: str
    purpose: str
    authorization_snapshot_digest: str
    items: list[ContextItem]
    context_pack_digest: str
    manifest_digest: str
    item_count: int
    byte_count: int
    status: str
    expires_at: datetime
    created_by: str
    created_at: datetime


class WorkingMemoryCreate(StrictModel):
    lease_token: str = Field(min_length=32, max_length=500)
    sequence: int = Field(ge=1)
    kind: Literal["observation", "decision", "scratch"]
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_path: str = Field(min_length=1, max_length=500)
    sensitivity: Literal["public", "internal", "restricted"] = "internal"
    expires_at: datetime

    @field_validator("workspace_path")
    @classmethod
    def relative_safe_path(cls, value: str) -> str:
        from pathlib import PurePosixPath

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("workspace_path must be task-relative")
        return value


class WorkingMemoryResponse(StrictModel):
    id: UUID
    context_manifest_id: UUID
    task_id: UUID
    agent_id: UUID
    sequence: int
    kind: str
    content_digest: str
    workspace_path: str
    sensitivity: str
    status: str
    expires_at: datetime
    receipt_digest: str
    discarded_at: datetime | None
    created_at: datetime


class ContextReplayRequest(StrictModel):
    lease_token: str = Field(min_length=32, max_length=500)
