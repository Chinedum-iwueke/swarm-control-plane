"""add M13 immutable data snapshots

Revision ID: e5f7a9b1c330
Revises: d4e6f8a0b220
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f7a9b1c330"
down_revision: str | None = "d4e6f8a0b220"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_data_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_key", sa.String(150), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["research_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_key"),
        sa.UniqueConstraint("content_digest"),
        sa.UniqueConstraint("record_digest"),
    )
    op.add_column(
        "research_experiments",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_experiments_snapshot_id",
        "research_experiments",
        "research_data_snapshots",
        ["snapshot_id"],
        ["id"],
    )
    op.execute(
        "CREATE TRIGGER research_data_snapshots_immutable BEFORE UPDATE OR DELETE "
        "ON research_data_snapshots FOR EACH ROW "
        "EXECUTE FUNCTION reject_research_record_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS research_data_snapshots_immutable "
        "ON research_data_snapshots"
    )
    op.drop_constraint(
        "fk_research_experiments_snapshot_id",
        "research_experiments",
        type_="foreignkey",
    )
    op.drop_column("research_experiments", "snapshot_id")
    op.drop_table("research_data_snapshots")
