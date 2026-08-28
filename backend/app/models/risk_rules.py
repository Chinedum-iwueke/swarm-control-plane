import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RiskRuleEvaluation(Base):
    __tablename__ = "risk_rule_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    reference_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reference_data_snapshots.id"),
        nullable=False,
        index=True,
    )
    risk_stress_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_stress_assessments.id"),
        nullable=False,
        index=True,
    )
    rule_pack_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    receipt: Mapped[dict] = mapped_column(JSONB, nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
