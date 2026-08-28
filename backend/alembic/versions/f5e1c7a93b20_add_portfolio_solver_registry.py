"""add portfolio solver registry

Revision ID: f5e1c7a93b20
Revises: f4d9b3e57c10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f5e1c7a93b20"
down_revision = "f4d9b3e57c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_solver_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("producer", sa.String(length=240), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("specification_digest", sa.String(length=64), nullable=False),
        sa.Column("specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_portfolio_solver_name_version"),
        sa.UniqueConstraint("specification_digest"),
    )
    op.create_index(op.f("ix_portfolio_solver_registry_name"), "portfolio_solver_registry", ["name"], unique=False)
    op.create_index(op.f("ix_portfolio_solver_registry_specification_digest"), "portfolio_solver_registry", ["specification_digest"], unique=True)
    op.create_index(op.f("ix_portfolio_solver_registry_status"), "portfolio_solver_registry", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_solver_registry_status"), table_name="portfolio_solver_registry")
    op.drop_index(op.f("ix_portfolio_solver_registry_specification_digest"), table_name="portfolio_solver_registry")
    op.drop_index(op.f("ix_portfolio_solver_registry_name"), table_name="portfolio_solver_registry")
    op.drop_table("portfolio_solver_registry")
