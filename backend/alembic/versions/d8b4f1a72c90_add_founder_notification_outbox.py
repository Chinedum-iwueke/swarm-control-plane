"""add founder notification outbox

Revision ID: d8b4f1a72c90
Revises: c4a8e2d71f30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8b4f1a72c90"
down_revision: str | None = "c4a8e2d71f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "founder_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deduplication_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=150), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index(
        op.f("ix_founder_notifications_entity_id"),
        "founder_notifications",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_founder_notifications_kind"),
        "founder_notifications",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_founder_notifications_state"),
        "founder_notifications",
        ["state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_founder_notifications_state"),
        table_name="founder_notifications",
    )
    op.drop_index(
        op.f("ix_founder_notifications_kind"),
        table_name="founder_notifications",
    )
    op.drop_index(
        op.f("ix_founder_notifications_entity_id"),
        table_name="founder_notifications",
    )
    op.drop_table("founder_notifications")
