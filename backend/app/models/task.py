import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    task_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    project: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    objective: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        index=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        index=True,
    )

    risk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("founder_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engineering_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    milestone_step_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_graph_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_graph_nodes.id"), nullable=True, index=True
    )

    created_by: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    input_contract: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    expected_outputs: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    acceptance_criteria: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    approval_policy: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    required_capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    allowed_machines: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    leased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    lease_token_prefix: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )

    lease_token_digest: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    last_execution_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    result: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    failure: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
