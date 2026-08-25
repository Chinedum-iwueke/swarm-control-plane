"""add service catalog and reconciliation ledger

Revision ID: a4c7e1f92b60
Revises: c9d4f2a71e30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c7e1f92b60"
down_revision: str | None = "c9d4f2a71e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_catalog_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catalog_version", sa.String(40), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("source_repository", sa.String(200), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_version"),
        sa.UniqueConstraint("manifest_digest"),
    )
    op.create_table(
        "service_catalog_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prior_snapshot_id", postgresql.UUID(as_uuid=True)),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("activated_by", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["service_catalog_snapshots.id"]),
        sa.ForeignKeyConstraint(
            ["prior_snapshot_id"], ["service_catalog_snapshots.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_service_catalog_activations_snapshot_id",
        "service_catalog_activations",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_service_catalog_activations_is_current",
        "service_catalog_activations",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "service_catalog_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("observations", postgresql.JSONB(), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("observation_digest", sa.String(64), nullable=False),
        sa.Column("report_digest", sa.String(64), nullable=False),
        sa.Column(
            "reconciled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["service_catalog_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_digest"),
    )
    op.create_index(
        "ix_service_catalog_reconciliations_snapshot_id",
        "service_catalog_reconciliations",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_service_catalog_reconciliations_status",
        "service_catalog_reconciliations",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("service_catalog_reconciliations")
    op.drop_table("service_catalog_activations")
    op.drop_table("service_catalog_snapshots")
