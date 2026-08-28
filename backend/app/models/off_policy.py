import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OffPolicyProposalEvaluation(Base):
    __tablename__ = "off_policy_proposal_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    dataset_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offline_rl_dataset_contracts.id"),
        nullable=False,
        index=True,
    )
    selection_audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("selection_bias_audits.id"),
        nullable=False,
        index=True,
    )
    calibration_assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_calibration_assessments.id"),
        nullable=False,
        index=True,
    )
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposal_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluation_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
