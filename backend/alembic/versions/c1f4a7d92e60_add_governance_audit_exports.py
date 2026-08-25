"""add immutable governance audit exports

Revision ID: c1f4a7d92e60
Revises: b9e4c2d63a10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1f4a7d92e60"
down_revision: str | None = "b9e4c2d63a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_audit_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("requested_by", sa.String(150), nullable=False),
        sa.Column("event_count", sa.BigInteger(), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("public_key", sa.String(64), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("bundle", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_digest"),
    )
    op.create_index(
        "ix_governance_audit_exports_requested_by",
        "governance_audit_exports",
        ["requested_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_governance_audit_exports_requested_by",
        table_name="governance_audit_exports",
    )
    op.drop_table("governance_audit_exports")
