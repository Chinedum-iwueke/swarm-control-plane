import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ModelCalibrationAssessment(Base):
    __tablename__ = "model_calibration_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assessment_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_family_evaluations.id"),
        nullable=False,
        index=True,
    )
    dossier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_dossiers.id"),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(180), nullable=False)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    specification_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assessment_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    assessed_by: Mapped[str] = mapped_column(String(150), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
