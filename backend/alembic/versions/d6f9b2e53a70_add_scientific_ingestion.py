"""add quarantined scientific ingestion

Revision ID: d6f9b2e53a70
Revises: c5e8a1d42f60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d6f9b2e53a70"
down_revision: str | None = "c5e8a1d42f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scientific_ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(180), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("quarantine_uri", sa.String(1000), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("stage_report", postgresql.JSONB(), nullable=False),
        sa.Column(
            "published_object_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
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
            "status IN ('quarantined','scanned','extracted','recovered','validated',"
            "'published','remediation_required','rejected')",
            name="ck_scientific_ingestion_status",
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name="ck_scientific_ingestion_digest",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_digest"),
    )
    op.create_index(
        "ix_scientific_ingestion_project",
        "scientific_ingestion_jobs",
        ["project"],
    )
    op.create_index(
        "ix_scientific_ingestion_status",
        "scientific_ingestion_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scientific_ingestion_status", table_name="scientific_ingestion_jobs"
    )
    op.drop_index(
        "ix_scientific_ingestion_project", table_name="scientific_ingestion_jobs"
    )
    op.drop_table("scientific_ingestion_jobs")
