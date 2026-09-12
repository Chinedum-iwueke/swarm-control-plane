"""add real-time risk schema registry

Revision ID: e2b7c5f94d10
Revises: d1a6b4e83c90
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2b7c5f94d10"
down_revision = "d1a6b4e83c90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "realtime_risk_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name", "version", name="uq_realtime_risk_schema_name_version"
        ),
        sa.UniqueConstraint("specification_digest"),
    )
    op.create_index(
        "ix_realtime_risk_schema_registry_name",
        "realtime_risk_schema_registry",
        ["name"],
    )
    op.create_index(
        "ix_realtime_risk_schema_registry_specification_digest",
        "realtime_risk_schema_registry",
        ["specification_digest"],
    )
    op.create_index(
        "ix_realtime_risk_schema_registry_status",
        "realtime_risk_schema_registry",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_realtime_risk_schema_registry_status",
        table_name="realtime_risk_schema_registry",
    )
    op.drop_index(
        "ix_realtime_risk_schema_registry_specification_digest",
        table_name="realtime_risk_schema_registry",
    )
    op.drop_index(
        "ix_realtime_risk_schema_registry_name",
        table_name="realtime_risk_schema_registry",
    )
    op.drop_table("realtime_risk_schema_registry")
