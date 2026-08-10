from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EvidenceRetrievalProjection(Base):
    __tablename__ = "evidence_retrieval_projections"

    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        primary_key=True,
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    object_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    scientific_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False)
    lexical_terms: Mapped[dict] = mapped_column(JSONB, nullable=False)
    vector: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    graph_neighbors: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceRetrievalState(Base):
    __tablename__ = "evidence_retrieval_states"

    projection_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False)
    built_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
