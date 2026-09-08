"""add intelligence truth and reasoning evaluation

Revision ID: c1d7e4a92f60
Revises: fce8a3b52d10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d7e4a92f60"
down_revision = "fce8a3b52d10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "intelligence_evaluation_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_version", sa.String(100), nullable=False, unique=True),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("projection_digest", sa.String(64), nullable=False),
        sa.Column("item_manifest", postgresql.JSONB(), nullable=False),
        sa.Column("hidden_gold", postgresql.JSONB(), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "intelligence_evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "suite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_evaluation_suites.id"),
            nullable=False,
        ),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("projection_digest", sa.String(64), nullable=False),
        sa.Column("model_runtime_digest", sa.String(64), nullable=False),
        sa.Column("evaluator_id", sa.String(150), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("domain_results", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("response_digest", sa.String(64), nullable=False),
        sa.Column("evaluation_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_intelligence_evaluation_runs_status",
        "intelligence_evaluation_runs",
        ["status"],
    )
    op.create_table(
        "intelligence_evaluation_item_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intelligence_evaluation_runs.id"),
            nullable=False,
        ),
        sa.Column("item_key", sa.String(150), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("scores", postgresql.JSONB(), nullable=False),
        sa.Column("failure_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("response_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False, unique=True),
        sa.UniqueConstraint(
            "run_id", "item_key", name="uq_intelligence_result_run_item"
        ),
    )
    op.create_index(
        "ix_intelligence_evaluation_item_results_domain",
        "intelligence_evaluation_item_results",
        ["domain"],
    )


def downgrade():
    op.drop_table("intelligence_evaluation_item_results")
    op.drop_table("intelligence_evaluation_runs")
    op.drop_table("intelligence_evaluation_suites")
