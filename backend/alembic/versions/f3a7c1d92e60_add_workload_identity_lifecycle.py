"""add workload identity authorization and secrets lifecycle

Revision ID: f3a7c1d92e60
Revises: e8b3d6f02a50
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a7c1d92e60"
down_revision: str | None = "e8b3d6f02a50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("workload_identity_controls",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("enforcement_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False), sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("activated_by", sa.String(150)), sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("workload_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("charter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_charters.id"), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("role_packages.id"), nullable=False),
        sa.Column("version", sa.String(50), nullable=False), sa.Column("machine", sa.String(100), nullable=False), sa.Column("audience", sa.String(150), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False), sa.Column("accountable_owner", sa.String(150), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False), sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("revoked_by", sa.String(150)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("revocation_reason", sa.String(500)),
        sa.UniqueConstraint("agent_id", "version"))
    op.create_index("ix_workload_identities_agent_id", "workload_identities", ["agent_id"])
    op.create_index("ix_workload_identities_status", "workload_identities", ["status"])
    op.create_table("workload_identity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workload_identities.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("event_type", sa.String(40), nullable=False), sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("prior_event_digest", sa.String(64)), sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("identity_id", "sequence"))
    op.create_index("ix_workload_identity_events_identity_id", "workload_identity_events", ["identity_id"])
    op.create_table("workload_secret_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workload_identities.id"), nullable=False),
        sa.Column("logical_name", sa.String(150), nullable=False), sa.Column("version", sa.String(50), nullable=False), sa.Column("required_scope", sa.String(100), nullable=False),
        sa.Column("reference", sa.String(300), nullable=False), sa.Column("rotation_due_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("policy_digest", sa.String(64), nullable=False, unique=True), sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("identity_id", "logical_name", "version"))
    op.create_index("ix_workload_secret_policies_identity_id", "workload_secret_policies", ["identity_id"])
    op.create_table("workload_authorization_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workload_identities.id"), nullable=False),
        sa.Column("credential_prefix", sa.String(32), nullable=False), sa.Column("action", sa.String(150), nullable=False), sa.Column("required_scope", sa.String(100), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False), sa.Column("reason", sa.String(300), nullable=False), sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_workload_authorization_receipts_identity_id", "workload_authorization_receipts", ["identity_id"])
    op.create_table("workload_emergency_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workload_identities.id"), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False), sa.Column("reason", sa.String(500), nullable=False), sa.Column("approved_by", sa.String(150), nullable=False),
        sa.Column("independent_reviewer", sa.String(150), nullable=False), sa.Column("approval_reference", sa.String(200), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_workload_emergency_grants_identity_id", "workload_emergency_grants", ["identity_id"])
    op.add_column("agent_credentials", sa.Column("workload_identity_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("agent_credentials", sa.Column("rotation_parent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("agent_credentials", sa.Column("rotation_state", sa.String(30), server_default="active", nullable=False))
    op.add_column("agent_credentials", sa.Column("overlap_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_agent_credentials_workload_identity", "agent_credentials", "workload_identities", ["workload_identity_id"], ["id"])
    op.create_foreign_key("fk_agent_credentials_rotation_parent", "agent_credentials", "agent_credentials", ["rotation_parent_id"], ["id"])
    op.create_index("ix_agent_credentials_workload_identity_id", "agent_credentials", ["workload_identity_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_credentials_workload_identity_id", table_name="agent_credentials")
    op.drop_constraint("fk_agent_credentials_rotation_parent", "agent_credentials", type_="foreignkey")
    op.drop_constraint("fk_agent_credentials_workload_identity", "agent_credentials", type_="foreignkey")
    for column in ("overlap_expires_at", "rotation_state", "rotation_parent_id", "workload_identity_id"):
        op.drop_column("agent_credentials", column)
    for table in ("workload_emergency_grants", "workload_authorization_receipts", "workload_secret_policies", "workload_identity_events", "workload_identities", "workload_identity_controls"):
        op.drop_table(table)
