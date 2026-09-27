"""add codex auth recovery

Revision ID: d3b9f5a72e10
Revises: d3b9f5a72e01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3b9f5a72e10"
down_revision: str | None = "d3b9f5a72e01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "codex_auth_recoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runtime_key", sa.String(120), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("verification_uri", sa.String(300)),
        sa.Column("device_code", sa.String(40)),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("retry_requested_at", sa.DateTime(timezone=True)),
        sa.Column("retry_acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("last_probe_at", sa.DateTime(timezone=True)),
        sa.Column("authenticated_at", sa.DateTime(timezone=True)),
        sa.Column("failure_summary", sa.Text()),
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
        sa.UniqueConstraint("runtime_key"),
    )
    op.create_index(
        "ix_codex_auth_recoveries_state", "codex_auth_recoveries", ["state"]
    )
    op.create_table(
        "codex_auth_recovery_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("recovery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recovery_id"], ["codex_auth_recoveries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_codex_auth_recovery_events_recovery_id",
        "codex_auth_recovery_events",
        ["recovery_id"],
    )
    op.create_index(
        "ix_codex_auth_recovery_events_event_type",
        "codex_auth_recovery_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_codex_auth_recovery_events_event_type",
        table_name="codex_auth_recovery_events",
    )
    op.drop_index(
        "ix_codex_auth_recovery_events_recovery_id",
        table_name="codex_auth_recovery_events",
    )
    op.drop_table("codex_auth_recovery_events")
    op.drop_index("ix_codex_auth_recoveries_state", table_name="codex_auth_recoveries")
    op.drop_table("codex_auth_recoveries")
