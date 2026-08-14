"""add RI-009 domain curriculum and brain evaluation

Revision ID: c4a8e2d71f30
Revises: 9b3e6f8a2c10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4a8e2d71f30"
down_revision: str | None = "9b3e6f8a2c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_domain_curricula",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain_key", sa.String(length=150), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("project", sa.String(length=100), nullable=False),
        sa.Column("specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column("graph_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain_key", "version"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        op.f("ix_research_domain_curricula_domain_key"),
        "research_domain_curricula",
        ["domain_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_domain_curricula_project"),
        "research_domain_curricula",
        ["project"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_domain_curricula_status"),
        "research_domain_curricula",
        ["status"],
        unique=False,
    )
    op.create_table(
        "research_brain_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_version", sa.String(length=100), nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column("graph_manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("evaluation_set_digest", sa.String(length=64), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cases", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("review_due_days", sa.Integer(), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("evaluated_by", sa.String(length=150), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["curriculum_id"], ["research_domain_curricula.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("curriculum_id", "evaluation_version"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        op.f("ix_research_brain_evaluations_curriculum_id"),
        "research_brain_evaluations",
        ["curriculum_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_brain_evaluations_status"),
        "research_brain_evaluations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_research_brain_evaluations_status"),
        table_name="research_brain_evaluations",
    )
    op.drop_index(
        op.f("ix_research_brain_evaluations_curriculum_id"),
        table_name="research_brain_evaluations",
    )
    op.drop_table("research_brain_evaluations")
    op.drop_index(
        op.f("ix_research_domain_curricula_status"),
        table_name="research_domain_curricula",
    )
    op.drop_index(
        op.f("ix_research_domain_curricula_project"),
        table_name="research_domain_curricula",
    )
    op.drop_index(
        op.f("ix_research_domain_curricula_domain_key"),
        table_name="research_domain_curricula",
    )
    op.drop_table("research_domain_curricula")
