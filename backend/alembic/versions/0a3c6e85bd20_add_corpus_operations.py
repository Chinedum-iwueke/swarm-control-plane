"""add corpus security observability and recovery

Revision ID: 0a3c6e85bd20
Revises: f9b2d5e74c10
Create Date: 2026-08-10 16:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0a3c6e85bd20"
down_revision: str | None = "f9b2d5e74c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corpus_security_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(length=100), nullable=False),
        sa.Column("finding_code", sa.String(length=100), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("disposition", sa.String(length=30), nullable=False),
        sa.Column("remediation", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"], ["scientific_ingestion_jobs.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_corpus_security_findings_ingestion_job_id",
        "corpus_security_findings",
        ["ingestion_job_id"],
    )
    op.create_index(
        "ix_corpus_security_findings_project",
        "corpus_security_findings",
        ["project"],
    )
    op.create_index(
        "ix_corpus_security_findings_finding_code",
        "corpus_security_findings",
        ["finding_code"],
    )
    op.create_index(
        "ix_corpus_security_findings_severity",
        "corpus_security_findings",
        ["severity"],
    )
    op.create_table(
        "corpus_backups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("project", sa.String(length=100), nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.String(length=1000), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_digest"),
    )
    op.create_index("ix_corpus_backups_project", "corpus_backups", ["project"])
    op.create_table(
        "corpus_recovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("project", sa.String(length=100), nullable=False),
        sa.Column("backup_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["backup_id"], ["corpus_backups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_corpus_recovery_runs_operation",
        "corpus_recovery_runs",
        ["operation"],
    )
    op.create_index(
        "ix_corpus_recovery_runs_project", "corpus_recovery_runs", ["project"]
    )
    op.create_index(
        "ix_corpus_recovery_runs_status", "corpus_recovery_runs", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_corpus_recovery_runs_status", table_name="corpus_recovery_runs")
    op.drop_index("ix_corpus_recovery_runs_project", table_name="corpus_recovery_runs")
    op.drop_index("ix_corpus_recovery_runs_operation", table_name="corpus_recovery_runs")
    op.drop_table("corpus_recovery_runs")
    op.drop_index("ix_corpus_backups_project", table_name="corpus_backups")
    op.drop_table("corpus_backups")
    op.drop_index("ix_corpus_security_findings_severity", table_name="corpus_security_findings")
    op.drop_index("ix_corpus_security_findings_finding_code", table_name="corpus_security_findings")
    op.drop_index("ix_corpus_security_findings_project", table_name="corpus_security_findings")
    op.drop_index(
        "ix_corpus_security_findings_ingestion_job_id",
        table_name="corpus_security_findings",
    )
    op.drop_table("corpus_security_findings")
