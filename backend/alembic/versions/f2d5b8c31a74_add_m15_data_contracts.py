"""add M15 point-in-time data contracts

Revision ID: f2d5b8c31a74
Revises: e1c4a7b92d60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2d5b8c31a74"
down_revision: str | None = "e1c4a7b92d60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_dataset_manifests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manifest_key", sa.String(150), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_digest"),
        sa.UniqueConstraint("manifest_key"),
    )
    op.create_table(
        "research_dataset_builds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("build_key", sa.String(150), nullable=False),
        sa.Column("manifest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("builder_repository", sa.String(150), nullable=False),
        sa.Column("builder_commit", sa.String(64), nullable=False),
        sa.Column("builder_runtime", sa.String(300), nullable=False),
        sa.Column("output_uri", sa.String(1000), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("rebuild_content_digest", sa.String(64), nullable=False),
        sa.Column("quality_results", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("built_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["manifest_id"], ["research_dataset_manifests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("build_key"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_research_dataset_builds_manifest_id",
        "research_dataset_builds",
        ["manifest_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_dataset_builds_manifest_id",
        table_name="research_dataset_builds",
    )
    op.drop_table("research_dataset_builds")
    op.drop_table("research_dataset_manifests")
