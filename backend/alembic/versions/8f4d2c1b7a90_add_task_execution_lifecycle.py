"""Add task execution lifecycle

Revision ID: 8f4d2c1b7a90
Revises: 5ab642aedfa6
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8f4d2c1b7a90"
down_revision: str | None = "5ab642aedfa6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "required_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "allowed_machines",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "leased_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "lease_token_prefix",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "lease_token_digest",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "last_execution_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "failure",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "tasks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.add_column(
        "task_events",
        sa.Column(
            "attempt_number",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_tasks_lease_expires_at",
        "tasks",
        ["lease_expires_at"],
        unique=False,
    )

    op.create_index(
        "ix_tasks_lease_token_prefix",
        "tasks",
        ["lease_token_prefix"],
        unique=False,
    )

    op.create_index(
        "ix_tasks_queue_selection",
        "tasks",
        [
            "status",
            "priority",
            "created_at",
        ],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION prevent_task_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'task_events is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE TRIGGER task_events_append_only
        BEFORE UPDATE OR DELETE ON task_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_task_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS task_events_append_only
        ON task_events;
        """
    )

    op.execute(
        """
        DROP FUNCTION IF EXISTS prevent_task_event_mutation();
        """
    )

    op.drop_index(
        "ix_tasks_queue_selection",
        table_name="tasks",
    )

    op.drop_index(
        "ix_tasks_lease_token_prefix",
        table_name="tasks",
    )

    op.drop_index(
        "ix_tasks_lease_expires_at",
        table_name="tasks",
    )

    op.drop_column(
        "task_events",
        "attempt_number",
    )

    op.drop_column("tasks", "updated_at")
    op.drop_column("tasks", "failure")
    op.drop_column("tasks", "result")
    op.drop_column(
        "tasks",
        "last_execution_heartbeat_at",
    )
    op.drop_column("tasks", "lease_token_digest")
    op.drop_column("tasks", "lease_token_prefix")
    op.drop_column("tasks", "leased_at")
    op.drop_column("tasks", "max_attempts")
    op.drop_column("tasks", "allowed_machines")
    op.drop_column(
        "tasks",
        "required_capabilities",
    )
