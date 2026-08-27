import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FactorExperimentProgram(Base):
    __tablename__ = "factor_experiment_programs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    program_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_hypotheses.id"),
        nullable=False,
        index=True,
    )
    language_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    semantic_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    compiled: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compiled_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    supersedes_program_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("factor_experiment_programs.id"), nullable=True
    )
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
