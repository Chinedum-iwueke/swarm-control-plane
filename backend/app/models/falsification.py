import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MechanismPlan(Base):
    __tablename__ = "mechanism_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    discovery_map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_maps.id"), nullable=False, index=True
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_hypotheses.id"),
        nullable=False,
        index=True,
    )
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MechanismEvaluation(Base):
    __tablename__ = "mechanism_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mechanism_plans.id"), nullable=False, index=True
    )
    evaluation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    conclusion: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evaluation_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    supersedes_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mechanism_evaluations.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
