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


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_key: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    machine: Mapped[str | None] = mapped_column(String(100), index=True)
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(150), index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(120), nullable=False)
    progress_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="indeterminate"
    )
    progress_current: Mapped[int | None] = mapped_column(Integer)
    progress_total: Mapped[int | None] = mapped_column(Integer)
    progress_unit: Mapped[str | None] = mapped_column(String(40))
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    links: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_digest: Mapped[str | None] = mapped_column(String(64))
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OperationEvent(Base):
    __tablename__ = "operation_events"
    __table_args__ = (UniqueConstraint("operation_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    phase: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
