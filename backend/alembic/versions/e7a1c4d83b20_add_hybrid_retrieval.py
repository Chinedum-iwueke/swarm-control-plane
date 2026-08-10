"""add canonical hybrid retrieval projections

Revision ID: e7a1c4d83b20
Revises: d6f9b2e53a70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e7a1c4d83b20"
down_revision: str | None = "d6f9b2e53a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "canonical_identity_aliases",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.create_table(
        "evidence_retrieval_projections",
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("object_schema_version", sa.String(100), nullable=False),
        sa.Column("scientific_type", sa.String(40), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), nullable=False),
        sa.Column("lexical_terms", postgresql.JSONB(), nullable=False),
        sa.Column("vector", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column(
            "graph_neighbors",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("projection_version", sa.String(100), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["canonical_evidence_objects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("object_id"),
    )
    op.create_index(
        "ix_evidence_retrieval_project",
        "evidence_retrieval_projections",
        ["project"],
    )
    op.create_index(
        "ix_evidence_retrieval_access_class",
        "evidence_retrieval_projections",
        ["access_class"],
    )
    op.create_index(
        "ix_evidence_retrieval_scientific_type",
        "evidence_retrieval_projections",
        ["scientific_type"],
    )
    op.create_table(
        "evidence_retrieval_states",
        sa.Column("projection_name", sa.String(100), nullable=False),
        sa.Column("projection_version", sa.String(100), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column(
            "built_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("projection_name"),
    )


def downgrade() -> None:
    op.drop_table("evidence_retrieval_states")
    op.drop_index(
        "ix_evidence_retrieval_scientific_type",
        table_name="evidence_retrieval_projections",
    )
    op.drop_index(
        "ix_evidence_retrieval_access_class",
        table_name="evidence_retrieval_projections",
    )
    op.drop_index(
        "ix_evidence_retrieval_project",
        table_name="evidence_retrieval_projections",
    )
    op.drop_table("evidence_retrieval_projections")
    op.alter_column(
        "canonical_identity_aliases",
        "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
