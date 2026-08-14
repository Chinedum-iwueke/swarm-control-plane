"""index canonical evidence edge endpoints

Revision ID: 9b3e6f8a2c10
Revises: 8a2d5f7c1e40
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9b3e6f8a2c10"
down_revision: str | None = "8a2d5f7c1e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_canonical_evidence_edges_subject_id"),
        "canonical_evidence_edges",
        ["subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_canonical_evidence_edges_object_id"),
        "canonical_evidence_edges",
        ["object_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_canonical_evidence_edges_object_id"),
        table_name="canonical_evidence_edges",
    )
    op.drop_index(
        op.f("ix_canonical_evidence_edges_subject_id"),
        table_name="canonical_evidence_edges",
    )
