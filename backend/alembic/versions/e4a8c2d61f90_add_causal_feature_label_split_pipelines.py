"""add causal feature label split pipelines

Revision ID: e4a8c2d61f90
Revises: d3f7a2b41c60
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e4a8c2d61f90"
down_revision = "d3f7a2b41c60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "causal_dataset_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_key", sa.String(180), nullable=False, unique=True),
        sa.Column(
            "dataset_build_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("research_dataset_builds.id"),
            nullable=False,
        ),
        sa.Column(
            "factor_program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factor_experiment_programs.id"),
            nullable=False,
        ),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("compiled", postgresql.JSONB(), nullable=False),
        sa.Column("compiled_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_causal_dataset_pipelines_dataset_build_id",
        "causal_dataset_pipelines",
        ["dataset_build_id"],
    )
    op.create_index(
        "ix_causal_dataset_pipelines_factor_program_id",
        "causal_dataset_pipelines",
        ["factor_program_id"],
    )
    op.create_table(
        "causal_dataset_materializations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("materialization_key", sa.String(180), nullable=False, unique=True),
        sa.Column(
            "pipeline_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("causal_dataset_pipelines.id"),
            nullable=False,
        ),
        sa.Column("output_uri", sa.String(1000), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("fold_results", postgresql.JSONB(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("rebuild_content_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("built_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_causal_dataset_materializations_pipeline_id",
        "causal_dataset_materializations",
        ["pipeline_id"],
    )


def downgrade():
    op.drop_index(
        "ix_causal_dataset_materializations_pipeline_id",
        table_name="causal_dataset_materializations",
    )
    op.drop_table("causal_dataset_materializations")
    op.drop_index(
        "ix_causal_dataset_pipelines_factor_program_id",
        table_name="causal_dataset_pipelines",
    )
    op.drop_index(
        "ix_causal_dataset_pipelines_dataset_build_id",
        table_name="causal_dataset_pipelines",
    )
    op.drop_table("causal_dataset_pipelines")
