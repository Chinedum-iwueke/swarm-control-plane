"""Add founder intake proposals

Revision ID: b7e31f4c2a90
Revises: a1d9e5f63c20
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7e31f4c2a90"
down_revision: str | None = "a1d9e5f63c20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "founder_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planner_agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("proposal_digest", sa.String(64), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(150), nullable=True),
        sa.Column(
            "materialized_task_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["planner_agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["source_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["materialized_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("materialized_task_id"),
        sa.UniqueConstraint("source_task_id"),
    )
    op.create_index(
        "ix_founder_proposals_source_task_id",
        "founder_proposals",
        ["source_task_id"],
    )
    op.create_index(
        "ix_founder_proposals_planner_agent_id",
        "founder_proposals",
        ["planner_agent_id"],
    )
    op.create_index(
        "ix_founder_proposals_status", "founder_proposals", ["status"]
    )


def downgrade() -> None:
    op.drop_table("founder_proposals")
