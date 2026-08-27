"""add model family regime evaluations

Revision ID: e5b9d3f72a10
Revises: e4a8c2d61f90
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5b9d3f72a10"
down_revision = "e4a8c2d61f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_family_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evaluation_key", sa.String(180), nullable=False, unique=True),
        sa.Column(
            "materialization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("causal_dataset_materializations.id"),
            nullable=False,
        ),
        sa.Column(
            "selection_audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("selection_bias_audits.id"),
            nullable=False,
        ),
        sa.Column("protocol", postgresql.JSONB(), nullable=False),
        sa.Column("protocol_digest", sa.String(64), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("candidates_digest", sa.String(64), nullable=False),
        sa.Column("scorecard", postgresql.JSONB(), nullable=False),
        sa.Column("scorecard_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_model_family_evaluations_materialization_id",
        "model_family_evaluations",
        ["materialization_id"],
    )
    op.create_index(
        "ix_model_family_evaluations_selection_audit_id",
        "model_family_evaluations",
        ["selection_audit_id"],
    )


def downgrade():
    op.drop_index(
        "ix_model_family_evaluations_selection_audit_id",
        table_name="model_family_evaluations",
    )
    op.drop_index(
        "ix_model_family_evaluations_materialization_id",
        table_name="model_family_evaluations",
    )
    op.drop_table("model_family_evaluations")
