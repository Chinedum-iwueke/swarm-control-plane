import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SymbolicSearchRun(Base):
    __tablename__ = "symbolic_search_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    base_factor_program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("factor_experiment_programs.id"),
        nullable=False,
        index=True,
    )
    prompt_policy_bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_policy_bundles.id"), nullable=False
    )
    constraints: Mapped[dict] = mapped_column(JSONB, nullable=False)
    constraints_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closure: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SymbolicSearchCandidate(Base):
    __tablename__ = "symbolic_search_candidates"
    __table_args__ = (UniqueConstraint("run_id", "candidate_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("symbolic_search_runs.id"),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(180), nullable=False)
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposal_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    semantic_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    violations: Mapped[list] = mapped_column(JSONB, nullable=False)
    compiled: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    submitted_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
