"""Add versioned role packages and deployment inventory

Revision ID: e7a2b6c91f30
Revises: d3f1a8c9b420
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e7a2b6c91f30"
down_revision: str | None = "d3f1a8c9b420"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("source_repository", sa.String(200), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_digest"),
        sa.UniqueConstraint("name", "version"),
    )
    op.create_index("ix_role_packages_name", "role_packages", ["name"])
    op.create_table(
        "package_deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deployed_by", sa.String(150), nullable=False),
        sa.Column(
            "deployed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["package_id"], ["role_packages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "package_id"),
    )
    op.create_index(
        "ix_package_deployments_agent_id", "package_deployments", ["agent_id"]
    )
    op.create_index(
        "ix_package_deployments_package_id", "package_deployments", ["package_id"]
    )
    op.execute(
        """
        CREATE FUNCTION prevent_role_package_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'role_packages is immutable; UPDATE and DELETE are forbidden';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER role_packages_immutable
        BEFORE UPDATE OR DELETE ON role_packages
        FOR EACH ROW EXECUTE FUNCTION prevent_role_package_mutation();
        """
    )


def downgrade() -> None:
    op.drop_table("package_deployments")
    op.execute("DROP TRIGGER IF EXISTS role_packages_immutable ON role_packages")
    op.execute("DROP FUNCTION IF EXISTS prevent_role_package_mutation()")
    op.drop_table("role_packages")
