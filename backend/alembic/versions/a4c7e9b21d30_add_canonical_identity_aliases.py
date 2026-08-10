"""add canonical identity aliases

Revision ID: a4c7e9b21d30
Revises: f2d5b8c31a74
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c7e9b21d30"
down_revision: str | None = "f2d5b8c31a74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_identity_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_object_type", sa.String(length=100), nullable=False),
        sa.Column("namespace", sa.String(length=100), nullable=False),
        sa.Column("native_object_type", sa.String(length=100), nullable=False),
        sa.Column("alias_value", sa.String(length=300), nullable=False),
        sa.Column("producer_schema_version", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("namespace", "native_object_type", "alias_value"),
    )
    op.create_index(
        "ix_canonical_identity_aliases_object",
        "canonical_identity_aliases",
        ["canonical_object_id", "canonical_object_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_identity_aliases_object",
        table_name="canonical_identity_aliases",
    )
    op.drop_table("canonical_identity_aliases")
