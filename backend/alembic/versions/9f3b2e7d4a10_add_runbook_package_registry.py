"""add runbook package registry

Revision ID: 9f3b2e7d4a10
Revises: c8e2f7a41d90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9f3b2e7d4a10"
down_revision: str | None = "c8e2f7a41d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runbook_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(length=128), nullable=False),
        sa.Column("source_repository", sa.String(length=200), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_digest"),
        sa.UniqueConstraint("name", "version"),
    )
    op.create_index(
        op.f("ix_runbook_packages_name"),
        "runbook_packages",
        ["name"],
        unique=False,
    )
    op.create_table(
        "runbook_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=True),
        sa.Column("approval_reference", sa.String(length=150), nullable=True),
        sa.Column("previous_record_digest", sa.String(length=64), nullable=True),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("recorded_by", sa.String(length=150), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["package_id"], ["runbook_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id", "state"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        op.f("ix_runbook_promotions_package_id"),
        "runbook_promotions",
        ["package_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_runbook_promotions_package_id"),
        table_name="runbook_promotions",
    )
    op.drop_table("runbook_promotions")
    op.drop_index(op.f("ix_runbook_packages_name"), table_name="runbook_packages")
    op.drop_table("runbook_packages")
