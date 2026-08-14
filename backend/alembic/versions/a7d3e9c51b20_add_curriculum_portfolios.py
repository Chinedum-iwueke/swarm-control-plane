"""add immutable curriculum portfolios

Revision ID: a7d3e9c51b20
Revises: f1a6c8d42e70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a7d3e9c51b20"
down_revision: str | None = "f1a6c8d42e70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_curriculum_portfolios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("portfolio_key", sa.String(length=150), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("required_domain_keys", postgresql.JSONB(), nullable=False),
        sa.Column("curriculum_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evaluation_ids", postgresql.JSONB(), nullable=False),
        sa.Column("readiness_matrix", postgresql.JSONB(), nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column("graph_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_key", "version"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_curriculum_portfolios_key",
        "research_curriculum_portfolios",
        ["portfolio_key"],
    )
    op.create_index(
        "ix_research_curriculum_portfolios_status",
        "research_curriculum_portfolios",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_curriculum_portfolios_status",
        table_name="research_curriculum_portfolios",
    )
    op.drop_index(
        "ix_research_curriculum_portfolios_key",
        table_name="research_curriculum_portfolios",
    )
    op.drop_table("research_curriculum_portfolios")
