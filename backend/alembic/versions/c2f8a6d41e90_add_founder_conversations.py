"""add canonical founder conversations

Revision ID: c2f8a6d41e90
Revises: b6f2a9c41d80
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2f8a6d41e90"
down_revision: str | None = "b6f2a9c41d80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "founder_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("short_id", sa.String(12), nullable=False),
        sa.Column("founder_key", sa.String(160), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("project", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("working_summary", sa.Text(), nullable=False),
        sa.Column("current_specification", postgresql.JSONB(), nullable=False),
        sa.Column("specification_digest", sa.String(64)),
        sa.Column("revision", sa.Integer(), nullable=False),
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
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_id"),
    )
    op.create_index(
        "ix_founder_conversations_short_id",
        "founder_conversations",
        ["short_id"],
        unique=True,
    )
    op.create_index(
        "ix_founder_conversations_founder_key", "founder_conversations", ["founder_key"]
    )
    op.create_index(
        "ix_founder_conversations_status", "founder_conversations", ["status"]
    )
    op.create_table(
        "founder_conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("channel_message_id", sa.String(160)),
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["founder_conversations.id"]),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"], ["founder_conversation_messages.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence"),
        sa.UniqueConstraint("conversation_id", "channel_message_id"),
    )
    op.create_index(
        "ix_founder_conversation_messages_conversation_id",
        "founder_conversation_messages",
        ["conversation_id"],
    )
    op.create_table(
        "founder_conversation_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("prior_status", sa.String(30)),
        sa.Column("resulting_status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["founder_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_founder_conversation_events_conversation_id",
        "founder_conversation_events",
        ["conversation_id"],
    )
    op.add_column("tasks", sa.Column("conversation_id", postgresql.UUID(as_uuid=True)))
    op.add_column("tasks", sa.Column("conversation_revision", sa.Integer()))
    op.create_foreign_key(
        "fk_tasks_conversation_id",
        "tasks",
        "founder_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_conversation_id", "tasks", ["conversation_id"])
    op.add_column(
        "founder_proposals", sa.Column("conversation_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("founder_proposals", sa.Column("conversation_revision", sa.Integer()))
    op.create_foreign_key(
        "fk_founder_proposals_conversation_id",
        "founder_proposals",
        "founder_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_founder_proposals_conversation_id", "founder_proposals", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_founder_proposals_conversation_id", table_name="founder_proposals"
    )
    op.drop_constraint(
        "fk_founder_proposals_conversation_id", "founder_proposals", type_="foreignkey"
    )
    op.drop_column("founder_proposals", "conversation_revision")
    op.drop_column("founder_proposals", "conversation_id")
    op.drop_index("ix_tasks_conversation_id", table_name="tasks")
    op.drop_constraint("fk_tasks_conversation_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "conversation_revision")
    op.drop_column("tasks", "conversation_id")
    op.drop_table("founder_conversation_events")
    op.drop_table("founder_conversation_messages")
    op.drop_table("founder_conversations")
