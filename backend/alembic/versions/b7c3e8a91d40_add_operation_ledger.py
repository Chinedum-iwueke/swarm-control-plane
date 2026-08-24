"""add fleet-wide operation ledger

Revision ID: b7c3e8a91d40
Revises: f1a6d3c84b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c3e8a91d40"
down_revision: str | None = "f1a6d3c84b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_key", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("machine", sa.String(100)),
        sa.Column("owner_type", sa.String(40), nullable=False),
        sa.Column("owner_id", sa.String(150)),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(120), nullable=False),
        sa.Column("progress_mode", sa.String(20), nullable=False),
        sa.Column("progress_current", sa.Integer()),
        sa.Column("progress_total", sa.Integer()),
        sa.Column("progress_unit", sa.String(40)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancellable", sa.Boolean(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("error_summary", sa.Text()),
        sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_digest", sa.String(64)),
        sa.Column("record_digest", sa.String(64), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_key"),
    )
    for column in ("kind", "project", "machine", "owner_id", "state", "heartbeat_at"):
        op.create_index(f"ix_operations_{column}", "operations", [column])
    op.create_table(
        "operation_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"], ["operations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", "sequence"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_operation_events_operation_id", "operation_events", ["operation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_operation_events_operation_id", table_name="operation_events")
    op.drop_table("operation_events")
    for column in reversed(
        ("kind", "project", "machine", "owner_id", "state", "heartbeat_at")
    ):
        op.drop_index(f"ix_operations_{column}", table_name="operations")
    op.drop_table("operations")
