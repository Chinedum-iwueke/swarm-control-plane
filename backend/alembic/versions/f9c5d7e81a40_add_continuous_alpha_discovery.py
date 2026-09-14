"""add continuous alpha discovery

Revision ID: f9c5d7e81a40
Revises: e8b4c2d60f31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9c5d7e81a40"
down_revision: str | None = "e8b4c2d60f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpha_research_mandates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mandate_key", sa.String(180), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("mandate_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("cycle_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hypothesis_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("trial_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("approved_by", sa.String(150)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mandate_digest"),
        sa.UniqueConstraint("mandate_key", "version"),
    )
    op.create_index(
        "ix_alpha_research_mandates_mandate_key",
        "alpha_research_mandates",
        ["mandate_key"],
    )
    op.create_index(
        "ix_alpha_research_mandates_status", "alpha_research_mandates", ["status"]
    )
    op.create_index(
        "ix_alpha_research_mandates_valid_until",
        "alpha_research_mandates",
        ["valid_until"],
    )
    op.create_table(
        "alpha_discovery_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mandate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(60), nullable=False),
        sa.Column("next_action", sa.String(100), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("research_brief", postgresql.JSONB(), nullable=False),
        sa.Column("intelligence_task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("hypothesis_task_id", postgresql.UUID(as_uuid=True)),
        sa.Column("discovery_portfolio_id", postgresql.UUID(as_uuid=True)),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("cycle_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["mandate_id"], ["alpha_research_mandates.id"]),
        sa.ForeignKeyConstraint(["intelligence_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["hypothesis_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(
            ["discovery_portfolio_id"], ["discovery_portfolios.id"]
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["alpha_campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_digest"),
        sa.UniqueConstraint("mandate_id", "ordinal"),
    )
    op.create_index(
        "ix_alpha_discovery_cycles_mandate_id", "alpha_discovery_cycles", ["mandate_id"]
    )
    op.create_index(
        "ix_alpha_discovery_cycles_status", "alpha_discovery_cycles", ["status"]
    )
    op.create_table(
        "alpha_discovery_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_key", sa.String(180), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("disposition", sa.String(40), nullable=False),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cycle_id"], ["alpha_discovery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_digest"),
        sa.UniqueConstraint("cycle_id", "candidate_key"),
    )
    op.create_index(
        "ix_alpha_discovery_candidates_cycle_id",
        "alpha_discovery_candidates",
        ["cycle_id"],
    )
    op.create_index(
        "ix_alpha_discovery_candidates_disposition",
        "alpha_discovery_candidates",
        ["disposition"],
    )
    op.create_table(
        "alpha_discovery_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mandate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64)),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["mandate_id"], ["alpha_research_mandates.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["alpha_discovery_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_digest"),
        sa.UniqueConstraint("mandate_id", "sequence"),
    )
    op.create_index(
        "ix_alpha_discovery_events_mandate_id", "alpha_discovery_events", ["mandate_id"]
    )
    op.create_index(
        "ix_alpha_discovery_events_event_type", "alpha_discovery_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_table("alpha_discovery_events")
    op.drop_table("alpha_discovery_candidates")
    op.drop_table("alpha_discovery_cycles")
    op.drop_table("alpha_research_mandates")
