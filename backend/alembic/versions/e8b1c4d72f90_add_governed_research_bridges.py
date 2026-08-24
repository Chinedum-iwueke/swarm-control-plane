"""add governed research bridges

Revision ID: e8b1c4d72f90
Revises: d4a7c9e21b60
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8b1c4d72f90"
down_revision: str | None = "d4a7c9e21b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governed_research_bridges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("receipts", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_digest"),
    )
    op.create_index("ix_governed_research_bridges_state", "governed_research_bridges", ["state"])


def downgrade() -> None:
    op.drop_index("ix_governed_research_bridges_state", table_name="governed_research_bridges")
    op.drop_table("governed_research_bridges")
