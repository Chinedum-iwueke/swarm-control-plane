"""add operational memory notes

Revision ID: e1c4a7b92d60
Revises: b9d2e4f6a810
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1c4a7b92d60"
down_revision: str | None = "b9d2e4f6a810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_key", sa.String(150), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("affected_systems", postgresql.JSONB(), nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("proposed_owner", sa.String(150), nullable=False),
        sa.Column("deferral_reason", sa.Text(), nullable=True),
        sa.Column("milestone_refs", postgresql.JSONB(), nullable=False),
        sa.Column("repository_refs", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("assigned_to", sa.String(150), nullable=True),
        sa.Column("deferred_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_evidence", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
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
        sa.UniqueConstraint("note_key"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index("ix_operational_notes_status", "operational_notes", ["status"])
    op.create_index("ix_operational_notes_urgency", "operational_notes", ["urgency"])
    op.create_table(
        "operational_note_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("previous_status", sa.String(20), nullable=True),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["note_id"], ["operational_notes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_note_events_note_id", "operational_note_events", ["note_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_note_events_note_id", table_name="operational_note_events"
    )
    op.drop_table("operational_note_events")
    op.drop_index("ix_operational_notes_urgency", table_name="operational_notes")
    op.drop_index("ix_operational_notes_status", table_name="operational_notes")
    op.drop_table("operational_notes")
