"""add structured research memory exports

Revision ID: b9d2e4f6a810
Revises: a7c9e1f3b520
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b9d2e4f6a810"
down_revision: str | None = "a7c9e1f3b520"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_memory_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository", sa.String(150), nullable=False),
        sa.Column("repository_commit", sa.String(64), nullable=False),
        sa.Column("database_digest", sa.String(64), nullable=False),
        sa.Column("export", postgresql.JSONB(), nullable=False),
        sa.Column("export_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_digest"),
    )
    op.create_index(
        "ix_research_memory_exports_repository",
        "research_memory_exports",
        ["repository"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_memory_exports_repository",
        table_name="research_memory_exports",
    )
    op.drop_table("research_memory_exports")
