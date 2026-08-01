"""add daily supervised research programs

Revision ID: f6a8c2d41b70
Revises: e5f7a9b1c330
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a8c2d41b70"
down_revision: str | None = "e5f7a9b1c330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_key", sa.String(150), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("mandate", postgresql.JSONB(), nullable=False),
        sa.Column("schedule", postgresql.JSONB(), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_key"),
    )
    op.create_table(
        "research_daily_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_date", sa.Date(), nullable=False),
        sa.Column("question_key", sa.String(150), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("duplicate_hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("digest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["research_programs.id"]),
        sa.ForeignKeyConstraint(
            ["duplicate_hypothesis_id"], ["research_hypotheses.id"]
        ),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["research_hypotheses.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "cycle_date"),
    )
    op.create_index(
        "ix_research_daily_cycles_program_id", "research_daily_cycles", ["program_id"]
    )
    op.create_index(
        "ix_research_daily_cycles_status", "research_daily_cycles", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_research_daily_cycles_status", table_name="research_daily_cycles")
    op.drop_index(
        "ix_research_daily_cycles_program_id", table_name="research_daily_cycles"
    )
    op.drop_table("research_daily_cycles")
    op.drop_table("research_programs")
