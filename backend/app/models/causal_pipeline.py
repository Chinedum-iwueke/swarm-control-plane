import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CausalDatasetPipeline(Base):
    __tablename__ = "causal_dataset_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    dataset_build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_dataset_builds.id"),
        nullable=False,
        index=True,
    )
    factor_program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("factor_experiment_programs.id"),
        nullable=False,
        index=True,
    )
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    specification_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    compiled: Mapped[dict] = mapped_column(JSONB, nullable=False)
    compiled_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CausalDatasetMaterialization(Base):
    __tablename__ = "causal_dataset_materializations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    materialization_key: Mapped[str] = mapped_column(
        String(180), unique=True, nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_dataset_pipelines.id"),
        nullable=False,
        index=True,
    )
    output_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fold_results: Mapped[list] = mapped_column(JSONB, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    rebuild_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    built_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
