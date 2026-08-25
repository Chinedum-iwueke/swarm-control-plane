"""add lifecycle consequences

Revision ID: a8d3f1c52b90
Revises: f7c2a9d41e80
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8d3f1c52b90"
down_revision: str | None = "f7c2a9d41e80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lifecycle_consequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutional_lifecycle_events.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "command_id", postgresql.UUID(as_uuid=True), unique=True, nullable=False
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("prior_state", sa.String(40), nullable=False),
        sa.Column("resulting_state", sa.String(40), nullable=False),
        sa.Column("rollback_state", sa.String(40), nullable=False),
        sa.Column("approvers", postgresql.JSONB(), nullable=False),
        sa.Column("affected_descendants", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_epoch", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "reversed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lifecycle_consequences.id"),
        ),
        sa.Column(
            "reversal_of_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lifecycle_consequences.id"),
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("record_digest", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('promote','demote','quarantine','retire','reinstate')"
        ),
        sa.CheckConstraint("status IN ('active','reversed','expired','reversal')"),
    )
    op.create_index(
        "ix_lifecycle_consequences_action", "lifecycle_consequences", ["action"]
    )
    op.create_index(
        "ix_lifecycle_consequences_status", "lifecycle_consequences", ["status"]
    )


def downgrade() -> None:
    op.drop_table("lifecycle_consequences")
