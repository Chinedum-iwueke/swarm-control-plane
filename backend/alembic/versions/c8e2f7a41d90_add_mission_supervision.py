"""Add autonomous mission supervision

Revision ID: c8e2f7a41d90
Revises: b7e31f4c2a90
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8e2f7a41d90"
down_revision: str | None = "b7e31f4c2a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_status", sa.String(30), nullable=True),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_policy", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_approved_by", sa.String(150), nullable=True),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("next_reconcile_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "engineering_missions",
        sa.Column("supervision_exception", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_engineering_missions_supervision_status", "engineering_missions", ["supervision_status"])
    op.create_index("ix_engineering_missions_next_reconcile_at", "engineering_missions", ["next_reconcile_at"])


def downgrade() -> None:
    op.drop_index("ix_engineering_missions_next_reconcile_at", table_name="engineering_missions")
    op.drop_index("ix_engineering_missions_supervision_status", table_name="engineering_missions")
    for column in (
        "supervision_exception",
        "next_reconcile_at",
        "recovery_count",
        "supervision_approved_by",
        "supervision_approved_at",
        "supervision_policy",
        "supervision_status",
        "supervision_enabled",
    ):
        op.drop_column("engineering_missions", column)
