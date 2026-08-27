import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ModelFamilyEvaluation(Base):
    __tablename__ = "model_family_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    materialization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_dataset_materializations.id"),
        nullable=False,
        index=True,
    )
    selection_audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("selection_bias_audits.id"),
        nullable=False,
        index=True,
    )
    protocol: Mapped[dict] = mapped_column(JSONB, nullable=False)
    protocol_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False)
    candidates_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    scorecard: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scorecard_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
