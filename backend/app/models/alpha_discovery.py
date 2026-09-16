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


class AlphaResearchMandate(Base):
    __tablename__ = "alpha_research_mandates"
    __table_args__ = (UniqueConstraint("mandate_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mandate_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    specification: Mapped[dict] = mapped_column(JSONB, nullable=False)
    budget: Mapped[dict] = mapped_column(JSONB, nullable=False)
    mandate_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="awaiting_approval", index=True
    )
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlphaDiscoveryCycle(Base):
    __tablename__ = "alpha_discovery_cycles"
    __table_args__ = (UniqueConstraint("mandate_id", "ordinal"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alpha_research_mandates.id"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="running", index=True
    )
    phase: Mapped[str] = mapped_column(
        String(60), nullable=False, default="intelligence_synthesis"
    )
    next_action: Mapped[str] = mapped_column(String(100), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    research_brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    intelligence_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    hypothesis_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    discovery_portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_portfolios.id")
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_campaigns.id")
    )
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cycle_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AlphaFounderResearchIdea(Base):
    __tablename__ = "alpha_founder_research_ideas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_research_mandates.id"), nullable=False, index=True
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_discovery_cycles.id"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("founder_conversations.id"), index=True
    )
    submitted_by: Mapped[str] = mapped_column(String(150), nullable=False)
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idea_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AlphaDiscoveryCandidate(Base):
    __tablename__ = "alpha_discovery_candidates"
    __table_args__ = (UniqueConstraint("cycle_id", "candidate_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alpha_discovery_cycles.id"),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(180), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    document: Mapped[dict] = mapped_column(JSONB, nullable=False)
    disposition: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False)
    candidate_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlphaDiscoveryEvent(Base):
    __tablename__ = "alpha_discovery_events"
    __table_args__ = (UniqueConstraint("mandate_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alpha_research_mandates.id"),
        nullable=False,
        index=True,
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alpha_discovery_cycles.id")
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


class AlphaCandidateDataAdmission(Base):
    __tablename__ = "alpha_candidate_data_admissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alpha_discovery_candidates.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), unique=True, nullable=False
    )
    catalog_receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quantitative_producer_receipts.id"),
        nullable=False,
    )
    catalog_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assets: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="queued", index=True
    )
    receipt_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dataset_bindings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    failure: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
