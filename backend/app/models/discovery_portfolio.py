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


class DiscoveryPortfolio(Base):
    __tablename__ = "discovery_portfolios"
    __table_args__ = (UniqueConstraint("portfolio_key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    project: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_epoch: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="allocated", index=True
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    attention_used: Mapped[int] = mapped_column(Integer, nullable=False)
    allocation_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiscoveryPortfolioCandidate(Base):
    __tablename__ = "discovery_portfolio_candidates"
    __table_args__ = (UniqueConstraint("portfolio_id", "candidate_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_portfolios.id"),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(180), nullable=False)
    domain_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    cluster_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    scoring: Mapped[dict] = mapped_column(JSONB, nullable=False)
    selected: Mapped[bool] = mapped_column(nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    decision: Mapped[dict] = mapped_column(JSONB, nullable=False)
    candidate_digest: Mapped[str] = mapped_column(String(64), nullable=False)


class DiscoveryPortfolioEvent(Base):
    __tablename__ = "discovery_portfolio_events"
    __table_args__ = (UniqueConstraint("portfolio_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discovery_portfolios.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_digest: Mapped[str | None] = mapped_column(String(64))
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
