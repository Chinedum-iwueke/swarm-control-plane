import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReferenceDataSnapshot(Base):
    __tablename__ = "reference_data_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    supersedes_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reference_data_snapshots.id"), nullable=True
    )
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
