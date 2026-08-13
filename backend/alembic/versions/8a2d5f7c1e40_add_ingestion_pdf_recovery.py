"""add governed scientific ingestion PDF recovery

Revision ID: 8a2d5f7c1e40
Revises: 6e8a1c4d9b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8a2d5f7c1e40"
down_revision: str | None = "6e8a1c4d9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scientific_ingestion_recoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sanitized_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=100), nullable=False),
        sa.Column("receipt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued','processing','recovered','rejected','remediation_required')"
        ),
        sa.ForeignKeyConstraint(
            ["original_job_id"], ["scientific_ingestion_jobs.id"]
        ),
        sa.ForeignKeyConstraint(
            ["sanitized_job_id"], ["scientific_ingestion_jobs.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("original_job_id"),
    )
    op.create_index(
        "ix_ingestion_recovery_original",
        "scientific_ingestion_recoveries",
        ["original_job_id"],
    )
    op.create_index(
        "ix_ingestion_recovery_status",
        "scientific_ingestion_recoveries",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_recovery_status", table_name="scientific_ingestion_recoveries"
    )
    op.drop_index(
        "ix_ingestion_recovery_original", table_name="scientific_ingestion_recoveries"
    )
    op.drop_table("scientific_ingestion_recoveries")
