"""add real data alpha campaigns

Revision ID: e3f7a1c94b20
Revises: d2e8f5b13a70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e3f7a1c94b20"
down_revision: str | None = "d2e8f5b13a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpha_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_key", sa.String(180), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("discovery_portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovery_portfolios.id"), nullable=False),
        sa.Column("campaign_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(60), nullable=False),
        sa.Column("next_action", sa.String(80), nullable=False),
        sa.Column("hypothesis_count", sa.Integer(), nullable=False),
        sa.Column("trial_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("terminal_reason", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("campaign_key", "version", name="uq_alpha_campaign_key_version"),
    )
    op.create_index("ix_alpha_campaign_status", "alpha_campaigns", ["status"])
    op.create_index("ix_alpha_campaign_project", "alpha_campaigns", ["project"])
    op.create_table(
        "alpha_campaign_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alpha_campaigns.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("attempt_key", sa.String(180), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_digest", sa.String(64), nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovery_portfolio_candidates.id"), nullable=False),
        sa.Column("source_candidate_digest", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(180), nullable=False),
        sa.Column("hypothesis_digest", sa.String(64), nullable=False),
        sa.Column("dataset_build_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("research_dataset_builds.id"), nullable=False),
        sa.Column("dataset_digest", sa.String(64), nullable=False),
        sa.Column("governed_bridge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("governed_research_bridges.id")),
        sa.Column("trial_count", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("failure_stage", sa.String(60)),
        sa.Column("gate_report", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(), nullable=False),
        sa.Column("produced_by", sa.String(100), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "ordinal", name="uq_alpha_attempt_ordinal"),
        sa.UniqueConstraint("campaign_id", "attempt_key", name="uq_alpha_attempt_key"),
    )
    op.create_index("ix_alpha_attempt_campaign", "alpha_campaign_attempts", ["campaign_id"])
    op.create_index("ix_alpha_attempt_outcome", "alpha_campaign_attempts", ["outcome"])
    op.create_table(
        "alpha_campaign_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alpha_campaigns.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64)),
        sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "sequence", name="uq_alpha_event_sequence"),
    )
    op.create_index("ix_alpha_event_campaign", "alpha_campaign_events", ["campaign_id"])
    op.create_index("ix_alpha_event_type", "alpha_campaign_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("alpha_campaign_events")
    op.drop_table("alpha_campaign_attempts")
    op.drop_table("alpha_campaigns")
