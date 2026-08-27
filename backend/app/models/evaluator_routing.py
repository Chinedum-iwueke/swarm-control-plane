import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
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


class EvaluatorProfile(Base):
    __tablename__ = "evaluator_profiles"
    __table_args__ = (UniqueConstraint("agent_id", "profile_version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active", index=True
    )
    review_kinds: Mapped[list] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, nullable=False)
    machine: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_family: Mapped[str] = mapped_column(String(120), nullable=False)
    runtime: Mapped[str] = mapped_column(String(120), nullable=False)
    context_group: Mapped[str] = mapped_column(String(120), nullable=False)
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("role_packages.id"), nullable=False
    )
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attestation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    profile_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationRoute(Base):
    __tablename__ = "evaluation_routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    producer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    route_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    blocked_reason: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluatorAssignment(Base):
    __tablename__ = "evaluator_assignments"
    __table_args__ = (
        UniqueConstraint("route_id", "review_kind"),
        UniqueConstraint("route_id", "evaluator_profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_routes.id"),
        nullable=False,
        index=True,
    )
    evaluator_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluator_profiles.id"),
        nullable=False,
        index=True,
    )
    review_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="assigned", index=True
    )
    correlation_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assignment_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    review_id: Mapped[str | None] = mapped_column(String(150))
    review_digest: Mapped[str | None] = mapped_column(String(64))
    completed_by: Mapped[str | None] = mapped_column(String(150))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationRouteEvent(Base):
    __tablename__ = "evaluation_route_events"
    __table_args__ = (UniqueConstraint("route_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_routes.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_digest: Mapped[str | None] = mapped_column(String(64))
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvaluationIndependenceReceipt(Base):
    __tablename__ = "evaluation_independence_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_routes.id"),
        nullable=False,
        unique=True,
    )
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    assertion: Mapped[dict] = mapped_column(JSONB, nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    issued_by: Mapped[str] = mapped_column(String(150), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
