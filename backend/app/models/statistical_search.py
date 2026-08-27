import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StatisticalSearchCampaign(Base):
    __tablename__ = "statistical_search_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    factor_program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("factor_experiment_programs.id"),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    specification_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    proposed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    registered_by: Mapped[str] = mapped_column(String(150), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StatisticalSearchEvent(Base):
    __tablename__ = "statistical_search_events"
    __table_args__ = (UniqueConstraint("campaign_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("statistical_search_campaigns.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prior_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
