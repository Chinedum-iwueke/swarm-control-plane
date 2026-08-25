import uuid
from datetime import datetime

from sqlalchemy import (
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


class InstitutionalLifecycleProjection(Base):
    __tablename__ = "institutional_lifecycle_projections"
    __table_args__ = (UniqueConstraint("subject_type", "subject_id", "dimension"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_event_digest: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InstitutionalLifecycleEvent(Base):
    __tablename__ = "institutional_lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    projection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutional_lifecycle_projections.id"),
        nullable=False,
        index=True,
    )
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(80), nullable=False)
    prior_state: Mapped[str] = mapped_column(String(40), nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    authority_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("authority_decision_records.id"), nullable=False
    )
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resulting_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)
    prior_event_digest: Mapped[str | None] = mapped_column(String(64))
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
