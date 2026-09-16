"""add immutable selected-panel admission handoffs

Revision ID: c2a8e4f61d90
Revises: b1e7f9a03c62
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2a8e4f61d90"
down_revision: str | None = "b1e7f9a03c62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpha_candidate_data_admissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "catalog_receipt_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("catalog_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("assets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "receipt_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "dataset_bindings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("failure", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["alpha_discovery_candidates.id"]
        ),
        sa.ForeignKeyConstraint(
            ["catalog_receipt_id"], ["quantitative_producer_receipts.id"]
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        "ix_alpha_candidate_data_admissions_candidate_id",
        "alpha_candidate_data_admissions",
        ["candidate_id"],
    )
    op.create_index(
        "ix_alpha_candidate_data_admissions_status",
        "alpha_candidate_data_admissions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alpha_candidate_data_admissions_status",
        table_name="alpha_candidate_data_admissions",
    )
    op.drop_index(
        "ix_alpha_candidate_data_admissions_candidate_id",
        table_name="alpha_candidate_data_admissions",
    )
    op.drop_table("alpha_candidate_data_admissions")
