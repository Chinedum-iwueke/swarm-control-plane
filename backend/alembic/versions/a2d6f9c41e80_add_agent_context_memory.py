"""add provenance-bearing agent context and working memory

Revision ID: a2d6f9c41e80
Revises: f3a7c1d92e60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2d6f9c41e80"
down_revision: str | None = "f3a7c1d92e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_context_manifests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("authorization_snapshot_digest", sa.String(64), nullable=False),
        sa.Column("context_pack", postgresql.JSONB(), nullable=False),
        sa.Column("context_pack_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("task_id", "attempt_number"),
    )
    op.create_index(
        "ix_agent_context_manifests_task_id", "agent_context_manifests", ["task_id"]
    )
    op.create_index(
        "ix_agent_context_manifests_agent_id", "agent_context_manifests", ["agent_id"]
    )
    op.create_table(
        "agent_working_memory_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "context_manifest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_context_manifests.id"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("workspace_path", sa.String(500), nullable=False),
        sa.Column("sensitivity", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("discarded_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("context_manifest_id", "sequence"),
    )
    op.create_index(
        "ix_agent_working_memory_receipts_context_manifest_id",
        "agent_working_memory_receipts",
        ["context_manifest_id"],
    )
    op.create_index(
        "ix_agent_working_memory_receipts_task_id",
        "agent_working_memory_receipts",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_table("agent_working_memory_receipts")
    op.drop_table("agent_context_manifests")
