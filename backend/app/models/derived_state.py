from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DerivedStateReconciliation(Base):
    __tablename__ = "derived_state_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_epoch_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_epoch_target: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    changed_object_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    affected_projects: Mapped[list] = mapped_column(JSONB, nullable=False)
    affected_domains: Mapped[list] = mapped_column(JSONB, nullable=False)
    phase_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    timings_ms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    terminal_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    error_summary: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DerivedStateChange(Base):
    __tablename__ = "derived_state_changes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    entity_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mutation: Mapped[str] = mapped_column(String(10), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    affected_object_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    transaction_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reconciliation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("derived_state_reconciliations.id"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DerivedStatePhaseReceipt(Base):
    __tablename__ = "derived_state_phase_receipts"
    __table_args__ = (
        UniqueConstraint(
            "reconciliation_id", "phase", name="uq_derived_state_run_phase"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("derived_state_reconciliations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
