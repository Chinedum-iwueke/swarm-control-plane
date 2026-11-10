"""add provider capacity circuits

Revision ID: b8e5f0d32c71
Revises: a7d4e9c21b60
Create Date: 2026-11-10 10:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8e5f0d32c71"
down_revision: str | None = "a7d4e9c21b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_capacity_circuits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column(
            "blocked_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("probe_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("probe_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["probe_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )
    for column in (
        "provider",
        "state",
        "source_task_id",
        "probe_agent_id",
        "next_probe_at",
        "probe_expires_at",
    ):
        op.create_index(
            op.f(f"ix_provider_capacity_circuits_{column}"),
            "provider_capacity_circuits",
            [column],
            unique=column == "provider",
        )
    op.create_table(
        "provider_capacity_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("circuit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=150), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["circuit_id"], ["provider_capacity_circuits.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("circuit_id", "event_type", "created_at"):
        op.create_index(
            op.f(f"ix_provider_capacity_events_{column}"),
            "provider_capacity_events",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("provider_capacity_events")
    op.drop_table("provider_capacity_circuits")
