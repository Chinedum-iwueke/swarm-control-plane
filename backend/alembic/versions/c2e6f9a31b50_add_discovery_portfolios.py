"""add discovery portfolios

Revision ID: c2e6f9a31b50
Revises: b1d5e8f20a40
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c2e6f9a31b50"
down_revision = "b1d5e8f20a40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "discovery_portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_key", sa.String(180), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("source_epoch", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), server_default="allocated", nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("attention_used", sa.Integer(), nullable=False),
        sa.Column("allocation_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("portfolio_key", "version"),
    )
    op.create_index(
        "ix_discovery_portfolios_portfolio_key",
        "discovery_portfolios",
        ["portfolio_key"],
    )
    op.create_index(
        "ix_discovery_portfolios_project", "discovery_portfolios", ["project"]
    )
    op.create_index(
        "ix_discovery_portfolios_status", "discovery_portfolios", ["status"]
    )
    op.create_table(
        "discovery_portfolio_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_portfolios.id"),
            nullable=False,
        ),
        sa.Column("candidate_key", sa.String(180), nullable=False),
        sa.Column("domain_key", sa.String(150), nullable=False),
        sa.Column("cluster_key", sa.String(150), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("scoring", postgresql.JSONB(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("decision", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("portfolio_id", "candidate_key"),
    )
    op.create_index(
        "ix_discovery_portfolio_candidates_portfolio_id",
        "discovery_portfolio_candidates",
        ["portfolio_id"],
    )
    op.create_index(
        "ix_discovery_portfolio_candidates_domain_key",
        "discovery_portfolio_candidates",
        ["domain_key"],
    )
    op.create_index(
        "ix_discovery_portfolio_candidates_cluster_key",
        "discovery_portfolio_candidates",
        ["cluster_key"],
    )
    op.create_table(
        "discovery_portfolio_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_portfolios.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64), nullable=True),
        sa.Column("event_digest", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("portfolio_id", "sequence"),
    )
    op.create_index(
        "ix_discovery_portfolio_events_portfolio_id",
        "discovery_portfolio_events",
        ["portfolio_id"],
    )


def downgrade():
    op.drop_index(
        "ix_discovery_portfolio_events_portfolio_id",
        table_name="discovery_portfolio_events",
    )
    op.drop_table("discovery_portfolio_events")
    op.drop_index(
        "ix_discovery_portfolio_candidates_cluster_key",
        table_name="discovery_portfolio_candidates",
    )
    op.drop_index(
        "ix_discovery_portfolio_candidates_domain_key",
        table_name="discovery_portfolio_candidates",
    )
    op.drop_index(
        "ix_discovery_portfolio_candidates_portfolio_id",
        table_name="discovery_portfolio_candidates",
    )
    op.drop_table("discovery_portfolio_candidates")
    op.drop_index("ix_discovery_portfolios_status", table_name="discovery_portfolios")
    op.drop_index("ix_discovery_portfolios_project", table_name="discovery_portfolios")
    op.drop_index(
        "ix_discovery_portfolios_portfolio_key", table_name="discovery_portfolios"
    )
    op.drop_table("discovery_portfolios")
