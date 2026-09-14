import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class ScientificRepresentation(Base):
    __tablename__ = "scientific_representations"
    __table_args__ = (
        UniqueConstraint(
            "source_object_id",
            "representation_version",
            name="uq_scientific_representation_source_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    scientific_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    normalized_content: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parser_outputs: Mapped[list] = mapped_column(JSONB, nullable=False)
    uncertainties: Mapped[list] = mapped_column(JSONB, nullable=False)
    source_region_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificFidelityManifest(Base):
    __tablename__ = "scientific_fidelity_manifests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    representation_digests: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificAdjudication(Base):
    __tablename__ = "scientific_adjudications"
    __table_args__ = (
        UniqueConstraint(
            "representation_id",
            "reviewer_id",
            name="uq_scientific_adjudication_reviewer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_representations.id"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[str] = mapped_column(String(150), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    gold_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_region_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    independent_of_producer: Mapped[bool] = mapped_column(Boolean, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificAdjudicationEvent(Base):
    __tablename__ = "scientific_adjudication_events"
    __table_args__ = (
        UniqueConstraint(
            "adjudication_id",
            "sequence",
            name="uq_scientific_adjudication_event_sequence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    adjudication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_adjudications.id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificBenchmark(Base):
    __tablename__ = "scientific_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False)
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sample_seed: Mapped[str] = mapped_column(String(100), nullable=False)
    sample_spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sampled_representation_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    sample_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_intervals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    counts: Mapped[dict] = mapped_column(JSONB, nullable=False)
    adjudication_digests: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    evaluation_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificCorrectionProposal(Base):
    __tablename__ = "scientific_correction_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_representations.id"),
        nullable=False,
        index=True,
    )
    adjudication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scientific_adjudications.id"), nullable=False
    )
    proposed_version: Mapped[str] = mapped_column(String(80), nullable=False)
    proposed_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    proposer_id: Mapped[str] = mapped_column(String(150), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificCalculationReceipt(Base):
    __tablename__ = "scientific_calculation_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_representations.id"),
        nullable=False,
        index=True,
    )
    context_pack_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assurance_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expression_tree: Mapped[dict] = mapped_column(JSONB, nullable=False)
    substitutions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    units: Mapped[list] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    representation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    executed_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MathematicsContextPack(Base):
    __tablename__ = "mathematics_context_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False)
    representation_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    context_pack_digest: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MathematicsCapabilityProfile(Base):
    __tablename__ = "mathematics_capability_profiles"
    __table_args__ = (
        UniqueConstraint(
            "agent_role", "profile_version", name="uq_mathematics_capability_profile"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_role: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    profile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    corpus_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    representation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    demonstrated_tasks: Mapped[list] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    evaluated_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificAssuranceRequest(Base):
    __tablename__ = "scientific_assurance_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_representations.id"),
        nullable=False,
        index=True,
    )
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    expression_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    required_level: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificAssuranceAttempt(Base):
    __tablename__ = "scientific_assurance_attempts"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "provider_family",
            "extractor_version",
            name="uq_scientific_assurance_attempt_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_assurance_requests.id"),
        nullable=False,
        index=True,
    )
    provider_family: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    produced_by: Mapped[str] = mapped_column(String(150), nullable=False)
    independence_receipt_digest: Mapped[str | None] = mapped_column(String(64))
    independent_review_digest: Mapped[str | None] = mapped_column(String(64))
    independent_of_representation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    checks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    attempt_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScientificAssuranceReceipt(Base):
    __tablename__ = "scientific_assurance_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_assurance_requests.id"),
        unique=True,
        nullable=False,
    )
    representation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scientific_representations.id"),
        nullable=False,
        index=True,
    )
    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_evidence_objects.id"),
        nullable=False,
        index=True,
    )
    source_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_region_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expression_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assurance_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    deterministic_checks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attempt_digests: Mapped[list] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, nullable=False)
    claim_boundary: Mapped[str] = mapped_column(Text, nullable=False)
    record_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_by: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
