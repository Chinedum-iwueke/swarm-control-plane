"""add evidence memory lifecycle ledger

Revision ID: a4e7c9d21f60
Revises: c8f2a6d94e31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4e7c9d21f60"
down_revision: str | None = "c8f2a6d94e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_lifecycle_states",
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("successor_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retention_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hold_authority", sa.String(100), nullable=True),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("state IN ('active','consolidated','superseded','retracted','expired','deleted')", name="ck_evidence_lifecycle_state"),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.ForeignKeyConstraint(["successor_object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("object_id"),
    )
    op.create_index("ix_evidence_lifecycle_states_state", "evidence_lifecycle_states", ["state"])
    op.execute(
        """
        INSERT INTO evidence_lifecycle_states
            (object_id, state, retention_hold, effective_at, version)
        SELECT id, 'active', false, created_at, 1
        FROM canonical_evidence_objects
        """
    )
    op.create_table(
        "evidence_lifecycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("prior_state", sa.String(30), nullable=False),
        sa.Column("resulting_state", sa.String(30), nullable=False),
        sa.Column("successor_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("authority", sa.String(100), nullable=False),
        sa.Column("legal_basis", sa.String(500), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.ForeignKeyConstraint(["successor_object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index("ix_evidence_lifecycle_events_object", "evidence_lifecycle_events", ["object_id", "created_at"])
    op.create_index("ix_evidence_lifecycle_events_type", "evidence_lifecycle_events", ["event_type"])
    op.create_table(
        "evidence_consolidation_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("duplicate_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authority", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_object_id"], ["canonical_evidence_objects.id"]),
        sa.ForeignKeyConstraint(["duplicate_object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_table(
        "evidence_deletion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("legal_basis", sa.String(500), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(100), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index("ix_evidence_deletion_requests_status", "evidence_deletion_requests", ["status"])
    op.execute("CREATE UNIQUE INDEX uq_pending_evidence_deletion ON evidence_deletion_requests (object_id) WHERE status = 'pending'")
    op.create_table(
        "evidence_lifecycle_impact_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("impact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["evidence_lifecycle_events.id"]),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.execute(
        """
        CREATE TRIGGER trg_evidence_lifecycle_states_freshness
        AFTER INSERT OR UPDATE OR DELETE ON evidence_lifecycle_states
        FOR EACH STATEMENT EXECUTE FUNCTION bump_evidence_corpus_freshness()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_evidence_lifecycle_states_freshness ON evidence_lifecycle_states")
    op.drop_table("evidence_lifecycle_impact_reports")
    op.execute("DROP INDEX uq_pending_evidence_deletion")
    op.drop_index("ix_evidence_deletion_requests_status", table_name="evidence_deletion_requests")
    op.drop_table("evidence_deletion_requests")
    op.drop_table("evidence_consolidation_receipts")
    op.drop_index("ix_evidence_lifecycle_events_type", table_name="evidence_lifecycle_events")
    op.drop_index("ix_evidence_lifecycle_events_object", table_name="evidence_lifecycle_events")
    op.drop_table("evidence_lifecycle_events")
    op.drop_index("ix_evidence_lifecycle_states_state", table_name="evidence_lifecycle_states")
    op.drop_table("evidence_lifecycle_states")
