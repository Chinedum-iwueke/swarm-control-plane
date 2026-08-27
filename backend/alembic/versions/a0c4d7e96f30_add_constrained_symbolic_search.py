"""add constrained symbolic search

Revision ID: a0c4d7e96f30
Revises: f9b3c6d85e20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a0c4d7e96f30"
down_revision = "f9b3c6d85e20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "symbolic_search_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_key", sa.String(180), unique=True, nullable=False),
        sa.Column(
            "base_factor_program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factor_experiment_programs.id"),
            nullable=False,
        ),
        sa.Column(
            "prompt_policy_bundle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_policy_bundles.id"),
            nullable=False,
        ),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column("constraints_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("candidate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accepted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("closure", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("generated_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_symbolic_search_runs_base_factor_program_id",
        "symbolic_search_runs",
        ["base_factor_program_id"],
    )
    op.create_table(
        "symbolic_search_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("symbolic_search_runs.id"),
            nullable=False,
        ),
        sa.Column("candidate_key", sa.String(180), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("proposal_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("semantic_digest", sa.String(64), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("violations", postgresql.JSONB(), nullable=False),
        sa.Column("compiled", postgresql.JSONB(), nullable=False),
        sa.Column("validation_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("submitted_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", "candidate_key"),
    )
    op.create_index(
        "ix_symbolic_search_candidates_run_id", "symbolic_search_candidates", ["run_id"]
    )
    op.create_index(
        "ix_symbolic_search_candidates_semantic_digest",
        "symbolic_search_candidates",
        ["semantic_digest"],
    )
    op.create_index(
        "ix_symbolic_search_candidates_status", "symbolic_search_candidates", ["status"]
    )


def downgrade():
    op.drop_index(
        "ix_symbolic_search_candidates_status", table_name="symbolic_search_candidates"
    )
    op.drop_index(
        "ix_symbolic_search_candidates_semantic_digest",
        table_name="symbolic_search_candidates",
    )
    op.drop_index(
        "ix_symbolic_search_candidates_run_id", table_name="symbolic_search_candidates"
    )
    op.drop_table("symbolic_search_candidates")
    op.drop_index(
        "ix_symbolic_search_runs_base_factor_program_id",
        table_name="symbolic_search_runs",
    )
    op.drop_table("symbolic_search_runs")
