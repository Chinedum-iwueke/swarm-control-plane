"""add factor experiment language

Revision ID: e8a2b5c74d10
Revises: d7f1a4b63c90
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8a2b5c74d10"
down_revision = "d7f1a4b63c90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "factor_experiment_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("program_key", sa.String(180), nullable=False, unique=True),
        sa.Column(
            "hypothesis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_hypotheses.id"),
            nullable=False,
        ),
        sa.Column("language_version", sa.String(40), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("semantic_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("compiled", postgresql.JSONB(), nullable=False),
        sa.Column("compiled_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column(
            "supersedes_program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factor_experiment_programs.id"),
            nullable=True,
        ),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_factor_experiment_programs_hypothesis_id",
        "factor_experiment_programs",
        ["hypothesis_id"],
    )


def downgrade():
    op.drop_index(
        "ix_factor_experiment_programs_hypothesis_id",
        table_name="factor_experiment_programs",
    )
    op.drop_table("factor_experiment_programs")
