import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class AutonomousResearchSession(Base):
    __tablename__ = "autonomous_research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    task_graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_graphs.id"), unique=True, nullable=False
    )
    task_graph_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    agenda: Mapped[dict] = mapped_column(JSONB, nullable=False)
    agenda_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    budget: Mapped[dict] = mapped_column(JSONB, nullable=False)
    budget_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    reconcile_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_progress_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_progress_digest: Mapped[str | None] = mapped_column(String(64))
    terminal_reason: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    closeout: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutonomousResearchSessionEvent(Base):
    __tablename__ = "autonomous_research_session_events"
    __table_args__ = (UniqueConstraint("session_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("autonomous_research_sessions.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_digest: Mapped[str | None] = mapped_column(String(64))
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
