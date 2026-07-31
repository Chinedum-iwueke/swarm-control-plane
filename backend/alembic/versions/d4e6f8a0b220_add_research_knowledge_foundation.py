"""add research knowledge foundation

Revision ID: d4e6f8a0b220
Revises: b2c4d6e8f110
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e6f8a0b220"
down_revision: str | None = "b2c4d6e8f110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "research_documents",
    "research_chunks",
    "research_retrieval_evaluations",
    "research_briefs",
)


def upgrade() -> None:
    op.create_table(
        "research_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_key", sa.String(150), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("evidence_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(150), nullable=False),
        sa.Column("source_uri", sa.String(1000), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("ingested_by", sa.String(150), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key"),
        sa.UniqueConstraint("content_digest"),
    )
    op.create_index(
        "ix_research_documents_document_type", "research_documents", ["document_type"]
    )
    op.create_index(
        "ix_research_documents_evidence_type", "research_documents", ["evidence_type"]
    )
    op.create_table(
        "research_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(500), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_digest", sa.String(64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["research_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("text_digest"),
        sa.UniqueConstraint("document_id", "ordinal"),
    )
    op.create_index(
        "ix_research_chunks_document_id", "research_chunks", ["document_id"]
    )
    op.execute(
        "CREATE INDEX ix_research_chunks_fts ON research_chunks "
        "USING gin (to_tsvector('english', text))"
    )
    op.create_table(
        "research_retrieval_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_key", sa.String(150), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("question_set_digest", sa.String(64), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_key"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_retrieval_evaluations_corpus_digest",
        "research_retrieval_evaluations",
        ["corpus_digest"],
    )
    op.create_table(
        "research_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint("record_digest"),
    )
    for table in _TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_research_record_mutation()"
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
        op.drop_table(table)
