import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class IntelligenceEvaluationSuite(Base):
    __tablename__ = "intelligence_evaluation_suites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suite_version: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    item_manifest: Mapped[list] = mapped_column(JSONB, nullable=False)
    hidden_gold: Mapped[list] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntelligenceEvaluationRun(Base):
    __tablename__ = "intelligence_evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_evaluation_suites.id"),
        nullable=False,
    )
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    projection_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    model_runtime_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluator_id: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    domain_results: Mapped[dict] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, nullable=False)
    response_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntelligenceEvaluationItemResult(Base):
    __tablename__ = "intelligence_evaluation_item_results"
    __table_args__ = (
        UniqueConstraint("run_id", "item_key", name="uq_intelligence_result_run_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intelligence_evaluation_runs.id"),
        nullable=False,
    )
    item_key: Mapped[str] = mapped_column(String(150), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(60), nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    failure_reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    response_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
