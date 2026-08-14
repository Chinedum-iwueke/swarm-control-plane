from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ResearchDomainCurriculum(Base):
    __tablename__ = "research_domain_curricula"
    __table_args__ = (UniqueConstraint("domain_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchBrainEvaluation(Base):
    __tablename__ = "research_brain_evaluations"
    __table_args__ = (UniqueConstraint("curriculum_id", "evaluation_version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_domain_curricula.id"),
        nullable=False,
        index=True,
    )
    evaluation_version: Mapped[str] = mapped_column(String(100), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cases: Mapped[list] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    review_due_days: Mapped[int] = mapped_column(Integer, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
