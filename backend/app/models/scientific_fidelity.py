import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ScientificRepresentation(Base):
    __tablename__ = "scientific_representations"
    __table_args__ = (
        UniqueConstraint(
            "source_object_id",
            "representation_version",
            name="uq_scientific_representation_source_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    scientific_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parser_outputs: Mapped[list] = mapped_column(JSONB, nullable=False)
    uncertainties: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_region_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificFidelityManifest(Base):
    __tablename__ = "scientific_fidelity_manifests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    representation_digests: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
