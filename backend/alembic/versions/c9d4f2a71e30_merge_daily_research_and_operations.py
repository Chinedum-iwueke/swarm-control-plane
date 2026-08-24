"""Merge daily-research and operation-ledger migration heads.

Revision ID: c9d4f2a71e30
Revises: a8c4e1d72b90, b7c3e8a91d40
"""

from collections.abc import Sequence


revision: str = "c9d4f2a71e30"
down_revision: tuple[str, str] = ("a8c4e1d72b90", "b7c3e8a91d40")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
