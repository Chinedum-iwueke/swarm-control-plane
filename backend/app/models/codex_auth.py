import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CodexAuthRecovery(Base):
    __tablename__ = "codex_auth_recoveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    runtime_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_uri: Mapped[str | None] = mapped_column(String(300))
    device_code: Mapped[str | None] = mapped_column(String(40))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CodexAuthRecoveryEvent(Base):
    __tablename__ = "codex_auth_recovery_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recovery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("codex_auth_recoveries.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
