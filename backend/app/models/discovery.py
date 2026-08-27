import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DiscoveryMap(Base):
    __tablename__ = "discovery_maps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    map_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    document: Mapped[dict] = mapped_column(JSONB, nullable=False)
    map_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    semantic_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    supersedes_map_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_maps.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiscoveryMapEvent(Base):
    __tablename__ = "discovery_map_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_maps.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_event_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(150), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
