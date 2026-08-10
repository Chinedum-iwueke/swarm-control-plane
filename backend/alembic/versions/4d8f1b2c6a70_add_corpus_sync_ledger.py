"""add existing corpus synchronization ledger

Revision ID: 4d8f1b2c6a70
Revises: 3c7e9a1d5b40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4d8f1b2c6a70"
down_revision: str | None = "3c7e9a1d5b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "corpus_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("source_kind", sa.String(50), nullable=False),
        sa.Column("source_root", sa.String(500), nullable=False),
        sa.Column("inventory_digest", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("coverage_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('complete','attention_required')"),
        sa.CheckConstraint(
            "source_kind IN ('founder_inbox','legacy_hermes',"
            "'imported_prior_result','bulletproof_projection')"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inventory_digest"),
    )
    for column in ("project", "source_kind", "status"):
        op.create_index(f"ix_corpus_sync_runs_{column}", "corpus_sync_runs", [column])
    op.create_table(
        "corpus_sync_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_locator", sa.String(1000), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=True),
        sa.Column("classification", postgresql.JSONB(), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canonical_object_ids", postgresql.JSONB(), nullable=False),
        sa.Column("predecessor_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["corpus_sync_runs.id"]),
        sa.ForeignKeyConstraint(["ingestion_job_id"], ["scientific_ingestion_jobs.id"]),
        sa.ForeignKeyConstraint(["predecessor_item_id"], ["corpus_sync_items.id"]),
        sa.CheckConstraint(
            "disposition IN ('canonical','quarantined','duplicate',"
            "'superseded','excluded','failed')"
        ),
        sa.CheckConstraint(
            "access_class IN ('public','internal','restricted','protected')"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "source_locator"),
    )
    for column in ("run_id", "content_digest", "disposition"):
        op.create_index(f"ix_corpus_sync_items_{column}", "corpus_sync_items", [column])
    op.execute(
        """
        CREATE FUNCTION reject_corpus_sync_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'corpus synchronization receipts are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("corpus_sync_runs", "corpus_sync_items"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_corpus_sync_mutation()"
        )


def downgrade() -> None:
    for table in ("corpus_sync_items", "corpus_sync_runs"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_corpus_sync_mutation()")
    op.drop_table("corpus_sync_items")
    op.drop_table("corpus_sync_runs")
