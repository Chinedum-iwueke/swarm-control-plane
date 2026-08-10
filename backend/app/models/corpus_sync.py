import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CorpusSyncRun(Base):
    __tablename__ = "corpus_sync_runs"
    __table_args__ = (
        CheckConstraint("status IN ('complete','attention_required')"),
        CheckConstraint(
            "source_kind IN ('founder_inbox','legacy_hermes',"
            "'imported_prior_result','bulletproof_projection')"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_root: Mapped[str] = mapped_column(String(500), nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    coverage_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CorpusSyncItem(Base):
    __tablename__ = "corpus_sync_items"
    __table_args__ = (
        UniqueConstraint("run_id", "source_locator"),
        CheckConstraint(
            "disposition IN ('canonical','quarantined','duplicate',"
            "'superseded','excluded','failed')"
        ),
        CheckConstraint(
            "access_class IN ('public','internal','restricted','protected')"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_sync_runs.id"), nullable=False, index=True
    )
    source_locator: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_digest: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    classification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False)
    disposition: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    ingestion_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scientific_ingestion_jobs.id"), nullable=True
    )
    canonical_object_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    predecessor_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("corpus_sync_items.id"), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
