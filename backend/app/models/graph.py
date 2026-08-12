from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EvidenceGraphProjectionState(Base):
    __tablename__ = "evidence_graph_projection_states"

    projection_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    built_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceGraphProjectionNode(Base):
    __tablename__ = "evidence_graph_projection_nodes"

    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    object_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)


class EvidenceGraphProjectionEdge(Base):
    __tablename__ = "evidence_graph_projection_edges"

    edge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_edges.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provenance_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    access_class: Mapped[str] = mapped_column(String(30), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(100), nullable=False)


class CognitiveToolReceipt(Base):
    __tablename__ = "cognitive_tool_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_pack_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
