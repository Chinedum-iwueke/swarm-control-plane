"""add budgeted statistical search

Revision ID: f9b3c6d85e20
Revises: e8a2b5c74d10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f9b3c6d85e20"
down_revision = "e8a2b5c74d10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "statistical_search_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_key", sa.String(180), unique=True, nullable=False),
        sa.Column(
            "factor_program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factor_experiment_programs.id"),
            nullable=False,
        ),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("specification_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("proposed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("observed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("event_head_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_statistical_search_campaigns_factor_program_id",
        "statistical_search_campaigns",
        ["factor_program_id"],
    )
    op.create_table(
        "statistical_search_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("statistical_search_campaigns.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("prior_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("campaign_id", "sequence"),
    )
    op.create_index(
        "ix_statistical_search_events_campaign_id",
        "statistical_search_events",
        ["campaign_id"],
    )


def downgrade():
    op.drop_index(
        "ix_statistical_search_events_campaign_id",
        table_name="statistical_search_events",
    )
    op.drop_table("statistical_search_events")
    op.drop_index(
        "ix_statistical_search_campaigns_factor_program_id",
        table_name="statistical_search_campaigns",
    )
    op.drop_table("statistical_search_campaigns")
