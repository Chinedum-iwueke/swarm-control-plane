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


class EngineeringMission(Base):
    __tablename__ = "engineering_missions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    milestone_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(150), nullable=False)
    approval_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    approval_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    max_tasks: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supervision_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    supervision_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, index=True
    )
    supervision_policy: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    supervision_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    supervision_approved_by: Mapped[str | None] = mapped_column(String(150))
    recovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_reconcile_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    supervision_exception: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MissionEvent(Base):
    __tablename__ = "mission_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engineering_missions.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
