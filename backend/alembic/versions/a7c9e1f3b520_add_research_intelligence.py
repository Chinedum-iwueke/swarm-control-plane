"""add research intelligence domains and runs

Revision ID: a7c9e1f3b520
Revises: f6a8c2d41b70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c9e1f3b520"
down_revision: str | None = "f6a8c2d41b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "research_chunks_text_digest_key", "research_chunks", type_="unique"
    )
    op.create_table(
        "research_domain_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain_key", sa.String(150), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["research_retrieval_evaluations.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain_key", "version"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_domain_profiles_domain_key",
        "research_domain_profiles",
        ["domain_key"],
    )
    op.create_index(
        "ix_research_domain_profiles_status",
        "research_domain_profiles",
        ["status"],
    )
    op.create_table(
        "research_intelligence_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("selected_candidate", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["domain_profile_id"], ["research_domain_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_intelligence_runs_domain_profile_id",
        "research_intelligence_runs",
        ["domain_profile_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_intelligence_runs_domain_profile_id",
        table_name="research_intelligence_runs",
    )
    op.drop_table("research_intelligence_runs")
    op.drop_index(
        "ix_research_domain_profiles_status",
        table_name="research_domain_profiles",
    )
    op.drop_index(
        "ix_research_domain_profiles_domain_key",
        table_name="research_domain_profiles",
    )
    op.drop_table("research_domain_profiles")
    op.create_unique_constraint(
        "research_chunks_text_digest_key", "research_chunks", ["text_digest"]
    )
