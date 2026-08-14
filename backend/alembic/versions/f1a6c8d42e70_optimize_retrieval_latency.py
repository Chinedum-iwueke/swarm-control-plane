"""optimize retrieval freshness and candidate generation

Revision ID: f1a6c8d42e70
Revises: d8b4f1a72c90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a6c8d42e70"
down_revision: str | None = "d8b4f1a72c90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_corpus_freshness",
        sa.Column("corpus_name", sa.String(length=100), nullable=False),
        sa.Column("epoch", sa.BigInteger(), nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("corpus_name"),
    )
    op.execute(
        """
        INSERT INTO evidence_corpus_freshness
            (corpus_name, epoch, corpus_digest)
        SELECT
            'canonical-scientific',
            1,
            COALESCE(
                (SELECT corpus_digest FROM evidence_retrieval_states
                 WHERE projection_name = 'canonical-scientific'),
                repeat('0', 64)
            )
        """
    )
    op.add_column(
        "evidence_retrieval_states",
        sa.Column(
            "source_epoch",
            sa.BigInteger(),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column(
        "evidence_retrieval_states", "source_epoch", server_default=None
    )
    op.create_index(
        "ix_retrieval_projection_content_digest",
        "evidence_retrieval_projections",
        ["content_digest"],
    )
    op.create_index(
        "ix_retrieval_projection_scope",
        "evidence_retrieval_projections",
        ["project", "access_class", "object_schema_version", "scientific_type"],
    )
    op.create_index(
        "ix_retrieval_projection_aliases_gin",
        "evidence_retrieval_projections",
        ["aliases"],
        postgresql_using="gin",
    )
    op.execute(
        """
        CREATE INDEX ix_retrieval_projection_content_fts
        ON evidence_retrieval_projections
        USING gin (to_tsvector('simple', content_text))
        """
    )
    op.execute(
        """
        CREATE FUNCTION bump_evidence_corpus_freshness()
        RETURNS trigger AS $$
        DECLARE next_epoch bigint;
        BEGIN
            UPDATE evidence_corpus_freshness
            SET epoch = epoch + 1,
                corpus_digest =
                    md5(corpus_digest || ':' || (epoch + 1)::text || ':' || TG_TABLE_NAME)
                    || md5(TG_OP || ':' || txid_current()::text || ':' || (epoch + 1)::text),
                updated_at = now()
            WHERE corpus_name = 'canonical-scientific'
            RETURNING epoch INTO next_epoch;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "canonical_evidence_objects",
        "canonical_evidence_edges",
        "canonical_identity_aliases",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_freshness
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION bump_evidence_corpus_freshness()
            """
        )


def downgrade() -> None:
    for table in (
        "canonical_evidence_objects",
        "canonical_evidence_edges",
        "canonical_identity_aliases",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_freshness ON {table}")
    op.execute("DROP FUNCTION bump_evidence_corpus_freshness()")
    op.execute("DROP INDEX ix_retrieval_projection_content_fts")
    op.drop_index(
        "ix_retrieval_projection_aliases_gin",
        table_name="evidence_retrieval_projections",
    )
    op.drop_index(
        "ix_retrieval_projection_scope",
        table_name="evidence_retrieval_projections",
    )
    op.drop_index(
        "ix_retrieval_projection_content_digest",
        table_name="evidence_retrieval_projections",
    )
    op.drop_column("evidence_retrieval_states", "source_epoch")
    op.drop_table("evidence_corpus_freshness")
