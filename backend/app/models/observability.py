import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ServiceSLOState(Base):
    __tablename__ = "service_slo_states"
    __table_args__ = (UniqueConstraint("service_key", "indicator"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    service_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(60), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    objective: Mapped[dict] = mapped_column(JSONB, nullable=False)
    measurement: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    consecutive_breaches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    consecutive_healthy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class RoutedServiceAlert(Base):
    __tablename__ = "routed_service_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_key: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    service_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(60), nullable=False)
    owner: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    route: Mapped[str] = mapped_column(String(80), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    silenced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class AlertRoutingEvent(Base):
    __tablename__ = "alert_routing_events"
    __table_args__ = (UniqueConstraint("alert_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
