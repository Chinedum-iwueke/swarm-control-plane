"""add demo certification schema registry

Revision ID: c6f2a9d48b70
Revises: b5e1f8d37c40
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "c6f2a9d48b70"
down_revision = "b5e1f8d37c40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "demo_certification_schema_registry",
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
        sa.UniqueConstraint("name", "version", name="uq_demo_certification_schema_name_version"),
        sa.UniqueConstraint("specification_digest"),
    )
    for column in ("name", "specification_digest", "status"):
        op.create_index(f"ix_demo_certification_schema_registry_{column}", "demo_certification_schema_registry", [column])


def downgrade():
    for column in ("status", "specification_digest", "name"):
        op.drop_index(f"ix_demo_certification_schema_registry_{column}", table_name="demo_certification_schema_registry")
    op.drop_table("demo_certification_schema_registry")
