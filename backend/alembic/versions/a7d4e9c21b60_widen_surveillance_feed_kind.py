"""widen surveillance feed kind

Revision ID: a7d4e9c21b60
Revises: e4c7a9b25d10
Create Date: 2026-09-29 21:36:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7d4e9c21b60"
down_revision: str | None = "e4c7a9b25d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "surveillance_sources",
        "feed_kind",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "surveillance_sources",
        "feed_kind",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
