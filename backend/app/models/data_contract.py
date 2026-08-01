import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ResearchDatasetManifest(Base):
    __tablename__ = "research_dataset_manifests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    manifest_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchDatasetBuild(Base):
    __tablename__ = "research_dataset_builds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    build_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    manifest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_dataset_manifests.id"),
        nullable=False,
        index=True,
    )
    builder_repository: Mapped[str] = mapped_column(String(150), nullable=False)
    builder_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    builder_runtime: Mapped[str] = mapped_column(String(300), nullable=False)
    output_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    rebuild_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_results: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    built_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
