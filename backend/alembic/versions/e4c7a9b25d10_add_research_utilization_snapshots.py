"""add research utilization snapshots

Revision ID: e4c7a9b25d10
Revises: d3b9f5a72e10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4c7a9b25d10"
down_revision: str | None = "d3b9f5a72e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_utilization_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("machine", sa.String(length=100), nullable=False),
        sa.Column("sample_id", sa.String(length=100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("worker_budget", sa.Integer(), nullable=False),
        sa.Column("active_workers", sa.Integer(), nullable=False),
        sa.Column("queue_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("work_kind_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allocations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scheduler", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_commits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine", "sample_id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index("ix_research_utilization_snapshots_machine", "research_utilization_snapshots", ["machine"])
    op.create_index("ix_research_utilization_snapshots_observed_at", "research_utilization_snapshots", ["observed_at"])
    op.create_index("ix_research_utilization_snapshots_state", "research_utilization_snapshots", ["state"])


def downgrade() -> None:
    op.drop_index("ix_research_utilization_snapshots_state", table_name="research_utilization_snapshots")
    op.drop_index("ix_research_utilization_snapshots_observed_at", table_name="research_utilization_snapshots")
    op.drop_index("ix_research_utilization_snapshots_machine", table_name="research_utilization_snapshots")
    op.drop_table("research_utilization_snapshots")
