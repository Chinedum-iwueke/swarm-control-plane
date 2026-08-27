"""add point in time reference data

Revision ID: e2d7a4c91b60
Revises: d5a9c3e72f10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2d7a4c91b60"
down_revision: str | None = "d5a9c3e72f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_data_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_key", sa.String(length=150), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
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
            ["supersedes_snapshot_id"], ["reference_data_snapshots.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_digest"),
        sa.UniqueConstraint("snapshot_key"),
    )
    op.create_index(
        "ix_reference_data_snapshots_as_of",
        "reference_data_snapshots",
        ["as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reference_data_snapshots_as_of",
        table_name="reference_data_snapshots",
    )
    op.drop_table("reference_data_snapshots")
