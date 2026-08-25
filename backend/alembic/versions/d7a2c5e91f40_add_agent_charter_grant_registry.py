"""add agent charter capability and grant registry

Revision ID: d7a2c5e91f40
Revises: c1f4a7d92e60
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7a2c5e91f40"
down_revision: str | None = "c1f4a7d92e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table("agent_charters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False), sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_by", sa.String(150)), sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_charters.id")),
        sa.UniqueConstraint("agent_id", "version"))
    op.create_index("ix_agent_charters_agent_id", "agent_charters", ["agent_id"]); op.create_index("ix_agent_charters_status", "agent_charters", ["status"])
    op.create_table("agent_capability_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("charter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_charters.id"), nullable=False), sa.Column("capability", sa.String(100), nullable=False),
        sa.Column("machine", sa.String(100), nullable=False), sa.Column("task_types", postgresql.JSONB(), nullable=False), sa.Column("repositories", postgresql.JSONB(), nullable=False),
        sa.Column("risk_ceiling", sa.Integer(), nullable=False), sa.Column("accountable_owner", sa.String(150), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("granted_by", sa.String(150), nullable=False), sa.Column("reason", sa.String(500), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by", sa.String(150)), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("revocation_reason", sa.String(500)),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for column in ("agent_id", "charter_id", "capability", "status"): op.create_index(f"ix_agent_capability_grants_{column}", "agent_capability_grants", [column])
    op.create_table("agent_grant_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("grant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_capability_grants.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("event_type", sa.String(30), nullable=False), sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("prior_event_digest", sa.String(64)), sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("grant_id", "sequence"))
    op.create_index("ix_agent_grant_events_grant_id", "agent_grant_events", ["grant_id"])

def downgrade() -> None:
    op.drop_table("agent_grant_events"); op.drop_table("agent_capability_grants"); op.drop_table("agent_charters")
