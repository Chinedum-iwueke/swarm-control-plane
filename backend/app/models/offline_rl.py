import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OfflineRLDatasetContract(Base):
    __tablename__ = "offline_rl_dataset_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    dataset_build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_dataset_builds.id"),
        nullable=False,
        index=True,
    )
    contract: Mapped[dict] = mapped_column(JSONB, nullable=False)
    contract_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    audit: Mapped[dict] = mapped_column(JSONB, nullable=False)
    audit_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
