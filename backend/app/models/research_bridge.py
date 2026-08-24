from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GovernedResearchBridge(Base):
    __tablename__ = "governed_research_bridges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    proposal_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    receipts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
