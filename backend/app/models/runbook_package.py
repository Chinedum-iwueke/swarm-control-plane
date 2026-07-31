import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RunbookPackage(Base):
    __tablename__ = "runbook_packages"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    source_repository: Mapped[str] = mapped_column(String(200), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RunbookPromotion(Base):
    __tablename__ = "runbook_promotions"
    __table_args__ = (UniqueConstraint("package_id", "state"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runbook_packages.id"),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    previous_record_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    recorded_by: Mapped[str] = mapped_column(String(150), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
