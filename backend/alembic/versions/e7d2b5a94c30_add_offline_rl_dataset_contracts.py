"""add offline rl dataset contracts

Revision ID: e7d2b5a94c30
Revises: e6c1a4f83b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7d2b5a94c30"
down_revision: str | None = "e6c1a4f83b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offline_rl_dataset_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_key", sa.String(length=180), nullable=False),
        sa.Column("dataset_build_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contract_digest", sa.String(length=64), nullable=False),
        sa.Column("audit", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dataset_build_id"], ["research_dataset_builds.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_digest"),
        sa.UniqueConstraint("contract_key"),
    )
    op.create_index(
        op.f("ix_offline_rl_dataset_contracts_dataset_build_id"),
        "offline_rl_dataset_contracts",
        ["dataset_build_id"],
    )
    op.create_index(
        op.f("ix_offline_rl_dataset_contracts_status"),
        "offline_rl_dataset_contracts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_offline_rl_dataset_contracts_status"),
        table_name="offline_rl_dataset_contracts",
    )
    op.drop_index(
        op.f("ix_offline_rl_dataset_contracts_dataset_build_id"),
        table_name="offline_rl_dataset_contracts",
    )
    op.drop_table("offline_rl_dataset_contracts")
