"""add portfolio capacity schema registry

Revision ID: a7c3e9b58f60
Revises: f6b2d8a47e50
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7c3e9b58f60"
down_revision = "f6b2d8a47e50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_capacity_schema_registry",
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
        sa.UniqueConstraint("name", "version", name="uq_portfolio_capacity_schema_name_version"),
        sa.UniqueConstraint("specification_digest", name="uq_portfolio_capacity_schema_specification_digest"),
    )
    op.create_index(
        "ix_portfolio_capacity_schema_registry_name", "portfolio_capacity_schema_registry", ["name"]
    )
    op.create_index(
        "ix_portfolio_capacity_schema_registry_status", "portfolio_capacity_schema_registry", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_capacity_schema_registry_status", table_name="portfolio_capacity_schema_registry")
    op.drop_index("ix_portfolio_capacity_schema_registry_name", table_name="portfolio_capacity_schema_registry")
    op.drop_table("portfolio_capacity_schema_registry")
