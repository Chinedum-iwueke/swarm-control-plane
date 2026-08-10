"""add canonical evidence kernel

Revision ID: c5e8a1d42f60
Revises: a4c7e9b21d30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8a1d42f60"
down_revision: str | None = "a4c7e9b21d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "canonical_evidence_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("object_schema_version", sa.String(100), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("content_version", sa.String(150), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("producer", postgresql.JSONB(), nullable=False),
        sa.Column("supersedes_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("authority_class", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "schema_version ~ '^canonical-identity-v1\\.[0-9]+\\.[0-9]+$'",
            name="ck_canonical_identity_schema_v1",
        ),
        sa.CheckConstraint(
            "object_schema_version ~ '^canonical-evidence-v1\\.[0-9]+\\.[0-9]+$'",
            name="ck_canonical_evidence_schema_v1",
        ),
        sa.CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name="ck_canonical_evidence_digest",
        ),
        sa.CheckConstraint(
            "object_type IN ('source','edition','artifact','scientific_object','claim',"
            "'method','assumption','dataset','run','review','decision','belief','episode')",
            name="ck_canonical_evidence_object_type",
        ),
        sa.CheckConstraint(
            "access_class IN ('public','internal','restricted','protected')",
            name="ck_canonical_evidence_access_class",
        ),
        sa.CheckConstraint(
            "authority_class IN ('primary','derived','institutional','operational')",
            name="ck_canonical_evidence_authority_class",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_object_id"], ["canonical_evidence_objects.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_canonical_evidence_type", "canonical_evidence_objects", ["object_type"]
    )
    op.create_index(
        "ix_canonical_evidence_project", "canonical_evidence_objects", ["project"]
    )
    op.create_index(
        "ix_canonical_evidence_access", "canonical_evidence_objects", ["access_class"]
    )
    op.create_index(
        "ix_canonical_evidence_content",
        "canonical_evidence_objects",
        ["object_type", "content_digest"],
    )
    op.create_foreign_key(
        "fk_canonical_alias_object",
        "canonical_identity_aliases",
        "canonical_evidence_objects",
        ["canonical_object_id"],
        ["id"],
    )
    op.create_table(
        "canonical_evidence_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicate", sa.String(100), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["canonical_evidence_objects.id"]),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "predicate", "object_id"),
    )
    op.create_index(
        "ix_canonical_evidence_edges_object",
        "canonical_evidence_edges",
        ["object_id"],
    )
    op.create_index(
        "ix_canonical_evidence_edges_subject",
        "canonical_evidence_edges",
        ["subject_id"],
    )
    op.create_table(
        "canonical_evidence_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["object_id"], ["canonical_evidence_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_canonical_evidence_audit_object",
        "canonical_evidence_audit_events",
        ["object_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_evidence_audit_object",
        table_name="canonical_evidence_audit_events",
    )
    op.drop_table("canonical_evidence_audit_events")
    op.drop_index(
        "ix_canonical_evidence_edges_subject", table_name="canonical_evidence_edges"
    )
    op.drop_index(
        "ix_canonical_evidence_edges_object", table_name="canonical_evidence_edges"
    )
    op.drop_table("canonical_evidence_edges")
    op.drop_constraint(
        "fk_canonical_alias_object",
        "canonical_identity_aliases",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_canonical_evidence_content", table_name="canonical_evidence_objects"
    )
    op.drop_index(
        "ix_canonical_evidence_access", table_name="canonical_evidence_objects"
    )
    op.drop_index(
        "ix_canonical_evidence_project", table_name="canonical_evidence_objects"
    )
    op.drop_index(
        "ix_canonical_evidence_type", table_name="canonical_evidence_objects"
    )
    op.drop_table("canonical_evidence_objects")
