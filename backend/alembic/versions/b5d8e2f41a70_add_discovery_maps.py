"""add observation anomaly and opportunity maps

Revision ID: b5d8e2f41a70
Revises: a4f9c3d72e10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5d8e2f41a70"
down_revision: str | None = "a4f9c3d72e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovery_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("map_key", sa.String(180), nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("map_digest", sa.String(64), nullable=False),
        sa.Column("semantic_fingerprint", sa.String(64), nullable=False),
        sa.Column("supersedes_map_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["supersedes_map_id"], ["discovery_maps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("map_digest"),
        sa.UniqueConstraint("map_key"),
    )
    op.create_index("ix_discovery_maps_stage", "discovery_maps", ["stage"])
    op.create_index(
        "ix_discovery_maps_semantic_fingerprint",
        "discovery_maps",
        ["semantic_fingerprint"],
    )
    op.create_table(
        "discovery_map_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("previous_event_digest", sa.String(64), nullable=True),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(150), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["map_id"], ["discovery_maps.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_digest"),
    )
    op.create_index(
        "ix_discovery_map_events_map_id", "discovery_map_events", ["map_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_map_events_map_id", table_name="discovery_map_events")
    op.drop_table("discovery_map_events")
    op.drop_index("ix_discovery_maps_semantic_fingerprint", table_name="discovery_maps")
    op.drop_index("ix_discovery_maps_stage", table_name="discovery_maps")
    op.drop_table("discovery_maps")
