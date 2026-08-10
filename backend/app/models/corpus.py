from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CorpusSecurityFinding(Base):
    __tablename__ = "corpus_security_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ingestion_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_ingestion_jobs.id"),
        nullable=False,
        index=True,
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    finding_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(30), nullable=False)
    remediation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CorpusBackup(Base):
    __tablename__ = "corpus_backups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    storage_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CorpusRecoveryRun(Base):
    __tablename__ = "corpus_recovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    backup_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_backups.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

