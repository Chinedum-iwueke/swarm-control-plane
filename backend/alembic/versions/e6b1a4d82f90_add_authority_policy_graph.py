"""add authority policy graph

Revision ID: e6b1a4d82f90
Revises: c5e8a2f41d70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6b1a4d82f90"
down_revision: str | None = "c5e8a2f41d70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authority_policy_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_key", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("activated_by", sa.String(150)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_policy_snapshots.id")),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("policy_key", "version"),
    )
    op.create_index("ix_authority_policy_snapshots_policy_key", "authority_policy_snapshots", ["policy_key"])
    op.create_index("ix_authority_policy_snapshots_status", "authority_policy_snapshots", ["status"])
    op.create_index(
        "uq_authority_policy_one_active",
        "authority_policy_snapshots",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "authority_delegations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_policy_snapshots.id"), nullable=False),
        sa.Column("grantor_actor", sa.String(150), nullable=False),
        sa.Column("grantee_actor", sa.String(150), nullable=False),
        sa.Column("decision_types", postgresql.JSONB(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("max_risk", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_authority_delegations_policy_id", "authority_delegations", ["policy_id"])
    op.create_index("ix_authority_delegations_grantee_actor", "authority_delegations", ["grantee_actor"])
    op.create_index("ix_authority_delegations_status", "authority_delegations", ["status"])
    op.create_table(
        "authority_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_policy_snapshots.id"), nullable=False),
        sa.Column("rule_key", sa.String(120), nullable=False),
        sa.Column("requester", sa.String(150), nullable=False),
        sa.Column("approver", sa.String(150)),
        sa.Column("independent_reviewer", sa.String(150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("compensating_controls", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("terminal_disposition", sa.Text()),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_authority_exceptions_policy_id", "authority_exceptions", ["policy_id"])
    op.create_index("ix_authority_exceptions_status", "authority_exceptions", ["status"])
    op.create_table(
        "authority_decision_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_policy_snapshots.id"), nullable=False),
        sa.Column("decision_type", sa.String(100), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("object_id", sa.String(200), nullable=False),
        sa.Column("object_digest", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("effective_roles", postgresql.JSONB(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("risk_level", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("delegation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_delegations.id")),
        sa.Column("exception_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("authority_exceptions.id")),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_authority_decision_records_policy_id", "authority_decision_records", ["policy_id"])
    op.create_index("ix_authority_decision_records_decision_type", "authority_decision_records", ["decision_type"])
    op.create_index("ix_authority_decision_records_actor", "authority_decision_records", ["actor"])
    op.create_index("ix_authority_decision_records_outcome", "authority_decision_records", ["outcome"])


def downgrade() -> None:
    op.drop_table("authority_decision_records")
    op.drop_table("authority_exceptions")
    op.drop_table("authority_delegations")
    op.drop_table("authority_policy_snapshots")
