import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LifecycleConsequence(Base):
    __tablename__ = "lifecycle_consequences"
    __table_args__ = (
        CheckConstraint(
            "action IN ('promote','demote','quarantine','retire','reinstate')"
        ),
        CheckConstraint("status IN ('active','reversed','expired','reversal')"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutional_lifecycle_events.id"),
        unique=True,
        nullable=False,
    )
    command_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False, default="active"
    )
    prior_state: Mapped[str] = mapped_column(String(40), nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(40), nullable=False)
    rollback_state: Mapped[str] = mapped_column(String(40), nullable=False)
    approvers: Mapped[list] = mapped_column(JSONB, nullable=False)
    affected_descendants: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence_epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reversed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lifecycle_consequences.id")
    )
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lifecycle_consequences.id")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
