"""add shadow monitoring schema registry

Revision ID: c9f5a1d72b80
Revises: b8d4f0c69a71
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c9f5a1d72b80"
down_revision = "b8d4f0c69a71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shadow_monitoring_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "name", "version", name="uq_shadow_monitoring_schema_name_version"
        ),
        sa.UniqueConstraint(
            "specification_digest",
            name="uq_shadow_monitoring_schema_specification_digest",
        ),
    )
    op.create_index(
        "ix_shadow_monitoring_schema_registry_name",
        "shadow_monitoring_schema_registry",
        ["name"],
    )
    op.create_index(
        "ix_shadow_monitoring_schema_registry_status",
        "shadow_monitoring_schema_registry",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shadow_monitoring_schema_registry_status",
        table_name="shadow_monitoring_schema_registry",
    )
    op.drop_index(
        "ix_shadow_monitoring_schema_registry_name",
        table_name="shadow_monitoring_schema_registry",
    )
    op.drop_table("shadow_monitoring_schema_registry")
