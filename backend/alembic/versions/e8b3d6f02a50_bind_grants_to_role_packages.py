"""bind grants to exact role packages

Revision ID: e8b3d6f02a50
Revises: d7a2c5e91f40
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8b3d6f02a50"
down_revision: str | None = "d7a2c5e91f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("agent_capability_grants", sa.Column("package_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("""
        UPDATE agent_capability_grants AS grants SET package_id = selected.package_id
        FROM (SELECT DISTINCT ON (agent_id) agent_id, package_id FROM package_deployments
              WHERE is_active IS true ORDER BY agent_id, deployed_at DESC) AS selected
        WHERE selected.agent_id = grants.agent_id
    """)
    op.create_foreign_key("fk_agent_capability_grants_package_id", "agent_capability_grants", "role_packages", ["package_id"], ["id"])
    op.create_index("ix_agent_capability_grants_package_id", "agent_capability_grants", ["package_id"])
    op.alter_column("agent_capability_grants", "package_id", nullable=False)

def downgrade() -> None:
    op.drop_index("ix_agent_capability_grants_package_id", table_name="agent_capability_grants")
    op.drop_constraint("fk_agent_capability_grants_package_id", "agent_capability_grants", type_="foreignkey")
    op.drop_column("agent_capability_grants", "package_id")
