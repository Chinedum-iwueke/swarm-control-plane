"""add laboratory publications

Revision ID: d4a7c9e21b60
Revises: c2f8a6d41e90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4a7c9e21b60"
down_revision: str | None = "c2f8a6d41e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "laboratory_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trial_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("lineage", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_receipt", postgresql.JSONB(), nullable=False),
        sa.Column("projection_receipt", postgresql.JSONB(), nullable=False),
        sa.Column("memory_receipt", postgresql.JSONB(), nullable=False),
        sa.Column("failure", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["trial_id"], ["research_trials.id"]),
        sa.ForeignKeyConstraint(["result_id"], ["research_results.id"]),
        sa.ForeignKeyConstraint(["run_object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trial_id"),
        sa.UniqueConstraint("result_id"),
        sa.UniqueConstraint("request_digest"),
        sa.UniqueConstraint("bundle_digest"),
    )
    op.create_index(
        "ix_laboratory_publications_state", "laboratory_publications", ["state"]
    )
    op.create_table(
        "laboratory_publication_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["publication_id"], ["laboratory_publications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", "sequence"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_laboratory_publication_events_publication_id",
        "laboratory_publication_events",
        ["publication_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_laboratory_publication_events_publication_id",
        table_name="laboratory_publication_events",
    )
    op.drop_table("laboratory_publication_events")
    op.drop_index(
        "ix_laboratory_publications_state", table_name="laboratory_publications"
    )
    op.drop_table("laboratory_publications")
