import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class QuantitativeProducerReceipt(Base):
    __tablename__ = "quantitative_producer_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    milestone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    producer: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    producer_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    receipt: Mapped[dict] = mapped_column(JSONB, nullable=False)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
