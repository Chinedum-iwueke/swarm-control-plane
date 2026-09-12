"""add execution safety schema registry

Revision ID: a4d9e7c26b30
Revises: f3c8d6a15e20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4d9e7c26b30"
down_revision = "f3c8d6a15e20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "execution_safety_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_execution_safety_schema_name_version"),
        sa.UniqueConstraint("specification_digest"),
    )
    for column in ("name", "specification_digest", "status"):
        op.create_index(f"ix_execution_safety_schema_registry_{column}", "execution_safety_schema_registry", [column])


def downgrade():
    for column in ("status", "specification_digest", "name"):
        op.drop_index(f"ix_execution_safety_schema_registry_{column}", table_name="execution_safety_schema_registry")
    op.drop_table("execution_safety_schema_registry")
