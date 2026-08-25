import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ServiceCatalogSnapshot(Base):
    __tablename__ = "service_catalog_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    catalog_version: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True
    )
    manifest_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_repository: Mapped[str] = mapped_column(String(200), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ServiceCatalogActivation(Base):
    __tablename__ = "service_catalog_activations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_catalog_snapshots.id"),
        nullable=False,
        index=True,
    )
    prior_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_catalog_snapshots.id")
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    activated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ServiceCatalogReconciliation(Base):
    __tablename__ = "service_catalog_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_catalog_snapshots.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    observations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    findings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    report_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
