from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EvidenceOppositionRecord(Base):
    __tablename__ = "evidence_opposition_records"
    __table_args__ = (
        UniqueConstraint("subject_claim_id", "opposing_object_id", "record_digest"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subject_claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    opposing_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    opposition_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    comparability: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_opposition_records.id"), nullable=True
    )
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    recorded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceOutcomeRecord(Base):
    __tablename__ = "evidence_outcome_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evidence_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    outcome_kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainty: Mapped[list] = mapped_column(JSONB, nullable=False)
    failure_mechanisms: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), nullable=False
    )
    affected_claim_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    recorded_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceDossier(Base):
    __tablename__ = "evidence_dossiers"
    __table_args__ = (UniqueConstraint("dossier_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dossier_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    decision_context: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_cutoff: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dossier: Mapped[dict] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    compiler_version: Mapped[str] = mapped_column(String(100), nullable=False)
    compiled_by: Mapped[str] = mapped_column(String(100), nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
