"""add lake governance and operations ledger

Revision ID: a4f9c3d72e10
Revises: f3e8b2c61d90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4f9c3d72e10"
down_revision: str | None = "f3e8b2c61d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lake_governance_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_key", sa.String(length=150), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("catalog_digest", sa.String(length=64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "supersedes_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_snapshot_id"], ["lake_governance_snapshots.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_digest"),
        sa.UniqueConstraint("snapshot_key"),
    )
    op.create_index(
        "ix_lake_governance_snapshots_as_of",
        "lake_governance_snapshots",
        ["as_of"],
        unique=False,
    )
    op.create_table(
        "lake_operation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("subject_key", sa.String(length=200), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("previous_event_digest", sa.String(length=64), nullable=True),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=150), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["lake_governance_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_digest"),
    )
    op.create_index(
        "ix_lake_operation_events_snapshot_id",
        "lake_operation_events",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_lake_operation_events_subject_key",
        "lake_operation_events",
        ["subject_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lake_operation_events_subject_key", table_name="lake_operation_events"
    )
    op.drop_index(
        "ix_lake_operation_events_snapshot_id", table_name="lake_operation_events"
    )
    op.drop_table("lake_operation_events")
    op.drop_index(
        "ix_lake_governance_snapshots_as_of",
        table_name="lake_governance_snapshots",
    )
    op.drop_table("lake_governance_snapshots")
