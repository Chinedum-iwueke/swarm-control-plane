from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CanonicalEvidenceObject(Base):
    __tablename__ = "canonical_evidence_objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    object_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content_version: Mapped[str] = mapped_column(String(150), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    producer: Mapped[dict] = mapped_column(JSONB, nullable=False)
    supersedes_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=True
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    access_class: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    authority_class: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    aliases: Mapped[list[CanonicalIdentityAlias]] = relationship(
        back_populates="canonical_object", lazy="selectin"
    )


class CanonicalIdentityAlias(Base):
    __tablename__ = "canonical_identity_aliases"
    __table_args__ = (
        UniqueConstraint("namespace", "native_object_type", "alias_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    canonical_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    namespace: Mapped[str] = mapped_column(String(100), nullable=False)
    native_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    alias_value: Mapped[str] = mapped_column(String(300), nullable=False)
    producer_schema_version: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    canonical_object: Mapped[CanonicalEvidenceObject] = relationship(
        back_populates="aliases"
    )


class CanonicalEvidenceEdge(Base):
    __tablename__ = "canonical_evidence_edges"
    __table_args__ = (
        UniqueConstraint("subject_id", "predicate", "object_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CanonicalEvidenceAuditEvent(Base):
    __tablename__ = "canonical_evidence_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
