"""add execution event schema registry

Revision ID: f8c2d4a71e90
Revises: f5e1c7a93b20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f8c2d4a71e90"
down_revision = "f5e1c7a93b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_event_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_execution_event_schema_name_version"),
        sa.UniqueConstraint("specification_digest", name="uq_execution_event_schema_digest"),
    )
    op.create_index("ix_execution_event_schema_status", "execution_event_schema_registry", ["status"])


def downgrade() -> None:
    op.drop_index("ix_execution_event_schema_status", table_name="execution_event_schema_registry")
    op.drop_table("execution_event_schema_registry")
