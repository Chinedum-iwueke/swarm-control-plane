from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SurveillanceSource(Base):
    __tablename__ = "surveillance_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    feed_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    domains: Mapped[list] = mapped_column(JSONB, nullable=False)
    rights: Mapped[str] = mapped_column(String(500), nullable=False)
    access_class: Mapped[str] = mapped_column(String(20), nullable=False)
    cadence: Mapped[str] = mapped_column(String(20), nullable=False)
    freshness_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    allowed_hosts: Mapped[list] = mapped_column(JSONB, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SurveillanceFetchReceipt(Base):
    __tablename__ = "surveillance_fetch_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surveillance_sources.id"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    connector_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)


class SurveillancePublication(Base):
    __tablename__ = "surveillance_publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surveillance_sources.id"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    publication_status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assessment: Mapped[dict] = mapped_column(JSONB, nullable=False)
    routing: Mapped[dict] = mapped_column(JSONB, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surveillance_publications.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SurveillanceDigest(Base):
    __tablename__ = "surveillance_digests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    week_ending: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retraction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SurveillanceRoutingEvent(Base):
    __tablename__ = "surveillance_routing_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surveillance_publications.id"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(String(2000), nullable=False)
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
