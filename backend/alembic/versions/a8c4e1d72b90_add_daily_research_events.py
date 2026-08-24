"""add daily research selection and approval events

Revision ID: a8c4e1d72b90
Revises: f1a6d3c84b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a8c4e1d72b90"
down_revision: str | None = "f1a6d3c84b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_daily_cycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cycle_id"], ["research_daily_cycles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "sequence"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        op.f("ix_research_daily_cycle_events_cycle_id"),
        "research_daily_cycle_events",
        ["cycle_id"],
    )
    op.create_index(
        op.f("ix_research_daily_cycle_events_event_type"),
        "research_daily_cycle_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_research_daily_cycle_events_event_type"),
        table_name="research_daily_cycle_events",
    )
    op.drop_index(
        op.f("ix_research_daily_cycle_events_cycle_id"),
        table_name="research_daily_cycle_events",
    )
    op.drop_table("research_daily_cycle_events")
