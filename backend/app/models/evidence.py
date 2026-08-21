from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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
    __table_args__ = (UniqueConstraint("subject_id", "predicate", "object_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provenance_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=True
    )
    access_class: Mapped[str] = mapped_column(
        String(30), nullable=False, default="internal"
    )
    record_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
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


class EvidenceLifecycleState(Base):
    __tablename__ = "evidence_lifecycle_states"

    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    successor_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=True
    )
    retention_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hold_authority: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def active_for_retrieval(self) -> bool:
        return self.state == "active"


class EvidenceLifecycleEvent(Base):
    __tablename__ = "evidence_lifecycle_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    prior_state: Mapped[str] = mapped_column(String(30), nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(30), nullable=False)
    successor_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=True
    )
    authority: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_basis: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceConsolidationReceipt(Base):
    __tablename__ = "evidence_consolidation_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    duplicate_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    authority: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvidenceDeletionRequest(Base):
    __tablename__ = "evidence_deletion_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceLifecycleImpactReport(Base):
    __tablename__ = "evidence_lifecycle_impact_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_lifecycle_events.id"), nullable=False
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_evidence_objects.id"), nullable=False
    )
    impact: Mapped[dict] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
