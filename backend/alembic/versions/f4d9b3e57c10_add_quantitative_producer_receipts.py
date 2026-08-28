"""add quantitative producer receipts

Revision ID: f4d9b3e57c10
Revises: f3c8a2e46b90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4d9b3e57c10"
down_revision: str | None = "f3c8a2e46b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quantitative_producer_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("milestone", sa.String(30), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("producer_version", sa.String(50), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("dataset_digest", sa.String(64), nullable=False),
        sa.Column("result_digest", sa.String(64), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("receipt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_digest"),
    )
    for column in (
        "milestone",
        "producer",
        "source_commit",
        "dataset_digest",
        "receipt_digest",
    ):
        op.create_index(
            op.f(f"ix_quantitative_producer_receipts_{column}"),
            "quantitative_producer_receipts",
            [column],
        )


def downgrade() -> None:
    for column in (
        "receipt_digest",
        "dataset_digest",
        "source_commit",
        "producer",
        "milestone",
    ):
        op.drop_index(
            op.f(f"ix_quantitative_producer_receipts_{column}"),
            table_name="quantitative_producer_receipts",
        )
    op.drop_table("quantitative_producer_receipts")
