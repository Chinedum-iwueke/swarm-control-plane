"""Add operational control scopes

Revision ID: d3f1a8c9b420
Revises: 8f4d2c1b7a90
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3f1a8c9b420"
down_revision: str | None = "8f4d2c1b7a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "control_scopes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_key", sa.String(length=150), nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=150), nullable=False),
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
        sa.UniqueConstraint("scope_type", "scope_key"),
    )
    op.create_index("ix_control_scopes_scope_type", "control_scopes", ["scope_type"])
    op.create_index("ix_control_scopes_scope_key", "control_scopes", ["scope_key"])
    op.create_table(
        "control_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_key", sa.String(length=150), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_control_events_scope_type", "control_events", ["scope_type"])
    op.create_index("ix_control_events_scope_key", "control_events", ["scope_key"])
    op.create_index("ix_control_events_event_type", "control_events", ["event_type"])
    op.create_index("ix_control_events_created_at", "control_events", ["created_at"])
    op.execute(
        """
        CREATE FUNCTION prevent_control_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'control_events is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER control_events_append_only
        BEFORE UPDATE OR DELETE ON control_events
        FOR EACH ROW EXECUTE FUNCTION prevent_control_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS control_events_append_only ON control_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_control_event_mutation()")
    op.drop_table("control_events")
    op.drop_table("control_scopes")
