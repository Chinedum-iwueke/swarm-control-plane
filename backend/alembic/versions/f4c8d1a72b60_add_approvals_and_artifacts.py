"""Add approvals and artifact registry

Revision ID: f4c8d1a72b60
Revises: e7a2b6c91f30
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f4c8d1a72b60"
down_revision: str | None = "e7a2b6c91f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "approval_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.alter_column("tasks", "approval_required", server_default=None)
    op.add_column(
        "tasks",
        sa.Column(
            "plan_digest",
            sa.String(64),
            server_default=sa.text("'" + ("0" * 64) + "'"),
            nullable=False,
        ),
    )
    op.alter_column("tasks", "plan_digest", server_default=None)
    op.create_table(
        "task_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("requested_by", sa.String(150), nullable=False),
        sa.Column("decided_by", sa.String(150)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("nonce_digest", sa.String(64)),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_task_approvals_status", "task_approvals", ["status"])
    op.create_table(
        "approval_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["approval_id"], ["task_approvals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_events_approval_id", "approval_events", ["approval_id"]
    )
    op.create_index("ix_approval_events_event_type", "approval_events", ["event_type"])
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("storage_backend", sa.String(30), nullable=False),
        sa.Column("workflow", sa.String(100), nullable=False),
        sa.Column("workflow_version", sa.String(50), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("confidentiality", sa.String(30), nullable=False),
        sa.Column("retention_class", sa.String(30), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("task_id", "agent_id", "artifact_type", "sha256"):
        op.create_index(f"ix_artifacts_{column}", "artifacts", [column])
    op.execute(
        """
        CREATE FUNCTION prevent_governance_evidence_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'governance evidence is append-only';
        END;
        $$;
        """
    )
    for table in ("approval_events", "artifacts"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_governance_evidence_mutation();"
        )


def downgrade() -> None:
    op.drop_table("artifacts")
    op.drop_table("approval_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_governance_evidence_mutation()")
    op.drop_table("task_approvals")
    op.drop_column("tasks", "plan_digest")
    op.drop_column("tasks", "approval_required")
