"""add governed scientific surveillance

Revision ID: 3c7e9a1d5b40
Revises: 0a3c6e85bd20
Create Date: 2026-08-10 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "3c7e9a1d5b40"
down_revision: str | None = "0a3c6e85bd20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "surveillance_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("source_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("feed_url", sa.String(2000), nullable=False),
        sa.Column("feed_kind", sa.String(20), nullable=False),
        sa.Column("domains", postgresql.JSONB(), nullable=False),
        sa.Column("rights", sa.String(500), nullable=False),
        sa.Column("access_class", sa.String(20), nullable=False),
        sa.Column("cadence", sa.String(20), nullable=False),
        sa.Column("freshness_hours", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("allowed_hosts", postgresql.JSONB(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key"),
    )
    op.create_index(
        "ix_surveillance_sources_project", "surveillance_sources", ["project"]
    )
    op.create_table(
        "surveillance_fetch_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("connector_version", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["surveillance_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_digest"),
    )
    op.create_index(
        "ix_surveillance_fetch_receipts_source_id",
        "surveillance_fetch_receipts",
        ["source_id"],
    )
    op.create_table(
        "surveillance_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("canonical_url", sa.String(2000), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_status", sa.String(20), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column("assessment", postgresql.JSONB(), nullable=False),
        sa.Column("routing", postgresql.JSONB(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["surveillance_sources.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["surveillance_publications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_digest"),
    )
    op.create_index(
        "ix_surveillance_publications_source_id",
        "surveillance_publications",
        ["source_id"],
    )
    op.create_index(
        "ix_surveillance_publications_project",
        "surveillance_publications",
        ["project"],
    )
    op.create_index(
        "ix_surveillance_publications_publication_status",
        "surveillance_publications",
        ["publication_status"],
    )
    op.create_table(
        "surveillance_routing_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(100), nullable=False),
        sa.Column("rationale", sa.String(2000), nullable=False),
        sa.Column("proposal", postgresql.JSONB(), nullable=False),
        sa.Column("event_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["publication_id"], ["surveillance_publications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_digest"),
    )
    op.create_index(
        "ix_surveillance_routing_events_publication_id",
        "surveillance_routing_events",
        ["publication_id"],
    )
    op.create_table(
        "surveillance_digests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("week_ending", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("correction_count", sa.Integer(), nullable=False),
        sa.Column("retraction_count", sa.Integer(), nullable=False),
        sa.Column("digest", postgresql.JSONB(), nullable=False),
        sa.Column("digest_sha256", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("digest_sha256"),
    )
    op.create_index(
        "ix_surveillance_digests_project", "surveillance_digests", ["project"]
    )


def downgrade() -> None:
    op.drop_index("ix_surveillance_digests_project", table_name="surveillance_digests")
    op.drop_table("surveillance_digests")
    op.drop_index(
        "ix_surveillance_routing_events_publication_id",
        table_name="surveillance_routing_events",
    )
    op.drop_table("surveillance_routing_events")
    op.drop_index(
        "ix_surveillance_publications_publication_status",
        table_name="surveillance_publications",
    )
    op.drop_index(
        "ix_surveillance_publications_source_id", table_name="surveillance_publications"
    )
    op.drop_index(
        "ix_surveillance_publications_project",
        table_name="surveillance_publications",
    )
    op.drop_table("surveillance_publications")
    op.drop_index(
        "ix_surveillance_fetch_receipts_source_id",
        table_name="surveillance_fetch_receipts",
    )
    op.drop_table("surveillance_fetch_receipts")
    op.drop_index("ix_surveillance_sources_project", table_name="surveillance_sources")
    op.drop_table("surveillance_sources")
