"""add constant-time graph freshness epoch

Revision ID: c8f2a6d94e31
Revises: a7d3e9c51b20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8f2a6d94e31"
down_revision: str | None = "a7d3e9c51b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_graph_projection_states",
        sa.Column(
            "source_epoch",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        """
        UPDATE evidence_graph_projection_states AS graph
        SET source_epoch = freshness.epoch
        FROM evidence_corpus_freshness AS freshness
        WHERE freshness.corpus_name = 'canonical-scientific'
          AND graph.projection_name = 'canonical-knowledge-graph'
          AND graph.built_at >= freshness.updated_at
        """
    )
    op.alter_column(
        "evidence_graph_projection_states",
        "source_epoch",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("evidence_graph_projection_states", "source_epoch")
