"""add scientific adjudication and learning loop

Revision ID: fbe7d2a41c90
Revises: fae4c6b93d20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fbe7d2a41c90"
down_revision = "fae4c6b93d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scientific_adjudications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "representation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scientific_representations.id"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(150), nullable=False),
        sa.Column("reviewer_role", sa.String(80), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("gold_payload", postgresql.JSONB(), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("source_region_digest", sa.String(64), nullable=False),
        sa.Column("independent_of_producer", sa.Boolean(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "representation_id",
            "reviewer_id",
            name="uq_scientific_adjudication_reviewer",
        ),
    )
    op.create_index(
        "ix_scientific_adjudication_representation",
        "scientific_adjudications",
        ["representation_id"],
    )
    op.create_index(
        "ix_scientific_adjudication_decision", "scientific_adjudications", ["decision"]
    )
    op.create_table(
        "scientific_adjudication_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "adjudication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scientific_adjudications.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64), nullable=False),
        sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "adjudication_id",
            "sequence",
            name="uq_scientific_adjudication_event_sequence",
        ),
    )
    op.create_index(
        "ix_scientific_adjudication_event_adjudication",
        "scientific_adjudication_events",
        ["adjudication_id"],
    )
    op.create_table(
        "scientific_benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("benchmark_version", sa.String(80), nullable=False),
        sa.Column("representation_version", sa.String(80), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("sample_seed", sa.String(100), nullable=False),
        sa.Column("sample_spec", postgresql.JSONB(), nullable=False),
        sa.Column("sampled_representation_ids", postgresql.JSONB(), nullable=False),
        sa.Column("sample_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("confidence_intervals", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("adjudication_digests", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluation_digest", sa.String(64), nullable=True, unique=True),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_scientific_benchmark_corpus", "scientific_benchmarks", ["corpus_digest"]
    )
    op.create_index(
        "ix_scientific_benchmark_status", "scientific_benchmarks", ["status"]
    )
    op.create_table(
        "scientific_correction_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "representation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scientific_representations.id"),
            nullable=False,
        ),
        sa.Column(
            "adjudication_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scientific_adjudications.id"),
            nullable=False,
        ),
        sa.Column("proposed_version", sa.String(80), nullable=False),
        sa.Column("proposed_payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("proposer_id", sa.String(150), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_scientific_correction_representation",
        "scientific_correction_proposals",
        ["representation_id"],
    )
    op.create_index(
        "ix_scientific_correction_status", "scientific_correction_proposals", ["status"]
    )


def downgrade() -> None:
    op.drop_table("scientific_correction_proposals")
    op.drop_table("scientific_benchmarks")
    op.drop_table("scientific_adjudication_events")
    op.drop_table("scientific_adjudications")
