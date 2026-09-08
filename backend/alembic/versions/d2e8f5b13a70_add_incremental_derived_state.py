"""add incremental derived-state orchestration

Revision ID: d2e8f5b13a70
Revises: c1d7e4a92f60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2e8f5b13a70"
down_revision: str | None = "c1d7e4a92f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "derived_state_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_epoch_start", sa.BigInteger(), nullable=False),
        sa.Column("source_epoch_target", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("phase", sa.String(80), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(150), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("changed_object_ids", postgresql.JSONB(), nullable=False),
        sa.Column("affected_projects", postgresql.JSONB(), nullable=False),
        sa.Column("affected_domains", postgresql.JSONB(), nullable=False),
        sa.Column("phase_results", postgresql.JSONB(), nullable=False),
        sa.Column("timings_ms", postgresql.JSONB(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("terminal_digest", sa.String(64), nullable=True, unique=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_derived_state_reconciliations_target",
        "derived_state_reconciliations",
        ["source_epoch_target"],
    )
    op.create_index(
        "ix_derived_state_reconciliations_state",
        "derived_state_reconciliations",
        ["state"],
    )
    op.create_table(
        "derived_state_changes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_epoch", sa.BigInteger(), nullable=False),
        sa.Column("entity_kind", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("mutation", sa.String(10), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("affected_object_ids", postgresql.JSONB(), nullable=False),
        sa.Column("transaction_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "reconciliation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derived_state_reconciliations.id"),
            nullable=True,
        ),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_derived_state_changes_epoch", "derived_state_changes", ["source_epoch"]
    )
    op.create_index(
        "ix_derived_state_changes_project", "derived_state_changes", ["project"]
    )
    op.create_index(
        "ix_derived_state_changes_reconciliation",
        "derived_state_changes",
        ["reconciliation_id"],
    )
    op.create_table(
        "derived_state_phase_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reconciliation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("derived_state_reconciliations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "reconciliation_id", "phase", name="uq_derived_state_run_phase"
        ),
    )
    op.create_index(
        "ix_derived_state_phase_run",
        "derived_state_phase_receipts",
        ["reconciliation_id"],
    )
    op.add_column(
        "research_brain_evaluations",
        sa.Column(
            "case_specifications",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column(
        "research_brain_evaluations", "case_specifications", server_default=None
    )
    op.execute(
        """
        CREATE FUNCTION record_derived_state_change()
        RETURNS trigger AS $$
        DECLARE
            row_value record;
            next_epoch bigint;
            object_ids jsonb;
            project_value text;
            entity_value text;
        BEGIN
            IF TG_OP = 'DELETE' THEN row_value := OLD; ELSE row_value := NEW; END IF;
            SELECT epoch + 1 INTO next_epoch
            FROM evidence_corpus_freshness
            WHERE corpus_name = 'canonical-scientific';

            IF TG_TABLE_NAME = 'canonical_evidence_objects' THEN
                object_ids := jsonb_build_array(row_value.id::text);
                project_value := row_value.project;
                entity_value := row_value.id::text;
            ELSIF TG_TABLE_NAME = 'canonical_identity_aliases' THEN
                object_ids := jsonb_build_array(row_value.canonical_object_id::text);
                SELECT project INTO project_value FROM canonical_evidence_objects
                WHERE id = row_value.canonical_object_id;
                entity_value := row_value.id::text;
            ELSE
                object_ids := jsonb_build_array(row_value.subject_id::text, row_value.object_id::text);
                IF row_value.provenance_object_id IS NOT NULL THEN
                    object_ids := object_ids || jsonb_build_array(row_value.provenance_object_id::text);
                END IF;
                SELECT project INTO project_value FROM canonical_evidence_objects
                WHERE id = row_value.subject_id;
                entity_value := row_value.id::text;
            END IF;

            INSERT INTO derived_state_changes
                (source_epoch, entity_kind, entity_id, mutation, project,
                 affected_object_ids, transaction_id)
            VALUES
                (COALESCE(next_epoch, 0), TG_TABLE_NAME, entity_value, lower(TG_OP),
                 COALESCE(project_value, '*'), object_ids, txid_current());
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "canonical_evidence_objects",
        "canonical_evidence_edges",
        "canonical_identity_aliases",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_derived_state_change
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION record_derived_state_change()
            """
        )


def downgrade() -> None:
    for table in (
        "canonical_evidence_objects",
        "canonical_evidence_edges",
        "canonical_identity_aliases",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_derived_state_change ON {table}")
    op.execute("DROP FUNCTION record_derived_state_change()")
    op.drop_column("research_brain_evaluations", "case_specifications")
    op.drop_table("derived_state_phase_receipts")
    op.drop_table("derived_state_changes")
    op.drop_table("derived_state_reconciliations")
