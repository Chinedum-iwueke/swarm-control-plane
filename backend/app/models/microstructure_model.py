import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MicrostructureModelRegistry(Base):
    __tablename__ = "microstructure_model_registry"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_microstructure_model_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    producer: Mapped[str] = mapped_column(String(240), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    specification_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
