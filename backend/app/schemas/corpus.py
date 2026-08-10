from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_DIGEST = r"^[0-9a-f]{64}$"
_NAME = r"^[a-z][a-z0-9._-]{0,99}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorpusBackupCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    created_by: str = Field(pattern=_NAME)


class CorpusBackupResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    schema_version: str
    project: str
    corpus_digest: str = Field(pattern=_DIGEST)
    manifest_digest: str = Field(pattern=_DIGEST)
    storage_uri: str
    object_count: int
    artifact_count: int
    byte_size: int
    created_by: str
    created_at: datetime


class CorpusRestoreCreate(StrictModel):
    confirmation: Literal["RESTORE_EMPTY_CORPUS"]
    requested_by: str = Field(pattern=_NAME)


class QueueRecoveryCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    requested_by: str = Field(pattern=_NAME)
    stale_after_seconds: int = Field(default=900, ge=60, le=86_400)


class ProjectionRecoveryCreate(StrictModel):
    project: str = Field(pattern=_NAME)
    requested_by: str = Field(pattern=_NAME)


class RecoveryRunResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    operation: str
    project: str
    backup_id: UUID | None
    status: Literal["succeeded", "failed"]
    evidence: dict
    evidence_digest: str = Field(pattern=_DIGEST)
    error_code: str | None
    started_at: datetime
    ended_at: datetime


class SecurityFindingResponse(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    ingestion_job_id: UUID
    project: str
    finding_code: str
    stage: str
    severity: str
    disposition: str
    remediation: dict
    recorded_at: datetime


class CorpusHealthResponse(StrictModel):
    project: str
    observed_at: datetime
    canonical_objects: int
    object_store_bytes: int
    ingestion_backlog: int
    rejected_jobs: int
    security_findings: int
    missing_artifacts: int
    projection_status: Literal["healthy", "missing", "stale", "corrupt"]
    projection_lag_seconds: float | None
    latest_backup_age_seconds: float | None
    latest_restore_age_seconds: float | None
    slo: dict[str, bool]
    healthy: bool
