import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ScientificIngestionJob(Base):
    __tablename__ = "scientific_ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(180), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    quarantine_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    stage_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    published_object_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
