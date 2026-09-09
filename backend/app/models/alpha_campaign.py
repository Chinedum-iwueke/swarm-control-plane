import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AlphaCampaign(Base):
    __tablename__ = "alpha_campaigns"
    __table_args__ = (UniqueConstraint("campaign_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    discovery_portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_portfolios.id"), nullable=False
    )
    campaign_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    budget: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="awaiting_activation", index=True
    )
    phase: Mapped[str] = mapped_column(String(60), nullable=False, default="approval")
    next_action: Mapped[str] = mapped_column(
        String(80), nullable=False, default="founder_activation"
    )
    hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    terminal_reason: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    candidate_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlphaCampaignAttempt(Base):
    __tablename__ = "alpha_campaign_attempts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "ordinal"),
        UniqueConstraint("campaign_id", "attempt_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_campaigns.id"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_key: Mapped[str] = mapped_column(String(180), nullable=False)
    attempt_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_portfolio_candidates.id"),
        nullable=False,
    )
    source_candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis_id: Mapped[str] = mapped_column(String(180), nullable=False)
    hypothesis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_build_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_dataset_builds.id"), nullable=False
    )
    dataset_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    governed_bridge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("governed_research_bridges.id")
    )
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    failure_stage: Mapped[str | None] = mapped_column(String(60))
    gate_report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list] = mapped_column(JSONB, nullable=False)
    produced_by: Mapped[str] = mapped_column(String(100), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlphaCampaignEvent(Base):
    __tablename__ = "alpha_campaign_events"
    __table_args__ = (UniqueConstraint("campaign_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_campaigns.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_digest: Mapped[str | None] = mapped_column(String(64))
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
