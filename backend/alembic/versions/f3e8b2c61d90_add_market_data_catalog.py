"""add immutable market data catalog

Revision ID: f3e8b2c61d90
Revises: e2d7a4c91b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3e8b2c61d90"
down_revision: str | None = "e2d7a4c91b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_catalog_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_key", sa.String(length=150), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("catalog", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("catalog_digest", sa.String(length=64), nullable=False),
        sa.Column("reference_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "supersedes_catalog_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_catalog_id"], ["market_data_catalog_snapshots.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_digest"),
        sa.UniqueConstraint("catalog_key"),
    )
    op.create_index(
        "ix_market_data_catalog_snapshots_as_of",
        "market_data_catalog_snapshots",
        ["as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_data_catalog_snapshots_as_of",
        table_name="market_data_catalog_snapshots",
    )
    op.drop_table("market_data_catalog_snapshots")
