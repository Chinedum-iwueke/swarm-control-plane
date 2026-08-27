import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SelectionBiasAudit(Base):
    __tablename__ = "selection_bias_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    audit_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    mechanism_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mechanism_evaluations.id"),
        nullable=False,
        index=True,
    )
    ledger: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ledger_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    audit: Mapped[dict] = mapped_column(JSONB, nullable=False)
    conclusion: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    audit_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supersedes_audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("selection_bias_audits.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    audited_by: Mapped[str] = mapped_column(String(150), nullable=False)
    audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
