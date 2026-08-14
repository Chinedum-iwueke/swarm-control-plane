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


class TaskApproval(Base):
    __tablename__ = "task_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(150))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    nonce_digest: Mapped[str | None] = mapped_column(String(64))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_approvals.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FounderNotification(Base):
    __tablename__ = "founder_notifications"
    __table_args__ = (UniqueConstraint("deduplication_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(150))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(30), nullable=False)
    workflow: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    confidentiality: Mapped[str] = mapped_column(String(30), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
