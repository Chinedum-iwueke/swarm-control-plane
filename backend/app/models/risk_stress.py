import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RiskStressAssessment(Base):
    __tablename__ = "risk_stress_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assessment_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    candidate_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    scenario_pack_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dossier: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dossier_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    assessed_by: Mapped[str] = mapped_column(String(150), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
