"""add immutable research registry

Revision ID: b2c4d6e8f110
Revises: 9f3b2e7d4a10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b2c4d6e8f110"
down_revision: str | None = "9f3b2e7d4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "research_sources",
    "research_hypotheses",
    "research_experiments",
    "research_reviews",
    "research_trials",
    "research_results",
    "research_decisions",
)


def _identity() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "research_sources",
        _identity(),
        sa.Column("source_key", sa.String(150), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        _timestamp("registered_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_table(
        "research_hypotheses",
        _identity(),
        sa.Column("hypothesis_key", sa.String(150), nullable=False),
        sa.Column("trial_family", sa.String(150), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        _timestamp("registered_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hypothesis_key"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_hypotheses_trial_family", "research_hypotheses", ["trial_family"]
    )
    op.create_table(
        "research_experiments",
        _identity(),
        sa.Column("experiment_key", sa.String(150), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        _timestamp("registered_at"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["research_hypotheses.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["research_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_key"),
        sa.UniqueConstraint("manifest_digest"),
    )
    op.create_index(
        "ix_research_experiments_hypothesis_id",
        "research_experiments",
        ["hypothesis_id"],
    )
    op.create_table(
        "research_reviews",
        _identity(),
        sa.Column("subject_type", sa.String(30), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("review_kind", sa.String(40), nullable=False),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("review", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("reviewer", sa.String(150), nullable=False),
        _timestamp("reviewed_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint("subject_type", "subject_id", "review_kind", "reviewer"),
    )
    op.create_index(
        "ix_research_reviews_subject_id", "research_reviews", ["subject_id"]
    )
    op.create_index(
        "ix_research_reviews_subject_type", "research_reviews", ["subject_type"]
    )
    op.create_table(
        "research_trials",
        _identity(),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trial_family", sa.String(150), nullable=False),
        sa.Column("run_id", sa.String(150), nullable=False),
        sa.Column("trial_number", sa.Integer(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("executed_by", sa.String(150), nullable=False),
        _timestamp("registered_at"),
        sa.ForeignKeyConstraint(["experiment_id"], ["research_experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint("run_id"),
        sa.UniqueConstraint("trial_family", "trial_number"),
    )
    op.create_index(
        "ix_research_trials_experiment_id", "research_trials", ["experiment_id"]
    )
    op.create_index(
        "ix_research_trials_trial_family", "research_trials", ["trial_family"]
    )
    op.create_table(
        "research_results",
        _identity(),
        sa.Column("trial_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(150), nullable=False),
        _timestamp("recorded_at"),
        sa.ForeignKeyConstraint(["trial_id"], ["research_trials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint("trial_id"),
    )
    op.create_index("ix_research_results_trial_id", "research_results", ["trial_id"])
    op.create_table(
        "research_decisions",
        _identity(),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(150), nullable=False),
        _timestamp("decided_at"),
        sa.ForeignKeyConstraint(["result_id"], ["research_results.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_decisions_result_id", "research_decisions", ["result_id"]
    )

    op.execute(
        """
        CREATE FUNCTION reject_research_record_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'research registry records are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_research_record_mutation()"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_research_record_mutation()")
    for table in reversed(_TABLES):
        op.drop_table(table)
