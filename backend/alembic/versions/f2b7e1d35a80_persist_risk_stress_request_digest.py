"""persist risk stress request digest

Revision ID: f2b7e1d35a80
Revises: f1a6d9c24e70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b7e1d35a80"
down_revision: str | None = "f1a6d9c24e70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The original endpoint could commit but could never serialize a response. Remove
    # those partial publications because their caller-supplied digest was not retained.
    op.execute("DELETE FROM risk_stress_assessments")
    op.add_column(
        "risk_stress_assessments",
        sa.Column("request_digest", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("risk_stress_assessments", "request_digest")
