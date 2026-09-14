"""add just-in-time scientific assurance

Revision ID: a0d6e8f92b51
Revises: f9c5d7e81a40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0d6e8f92b51"
down_revision: str | None = "f9c5d7e81a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scientific_assurance_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("representation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("expression_digest", sa.String(64), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("required_level", sa.String(40), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["scientific_representations.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cache_key"),
    )
    op.create_index(
        "ix_scientific_assurance_requests_representation_id",
        "scientific_assurance_requests",
        ["representation_id"],
    )
    op.create_index(
        "ix_scientific_assurance_requests_status",
        "scientific_assurance_requests",
        ["status"],
    )
    op.add_column(
        "scientific_calculation_receipts",
        sa.Column("assurance_receipt_digest", sa.String(64), nullable=True),
    )
    op.execute(
        "UPDATE scientific_calculation_receipts SET assurance_receipt_digest = "
        "repeat('0', 64) WHERE assurance_receipt_digest IS NULL"
    )
    op.alter_column(
        "scientific_calculation_receipts",
        "assurance_receipt_digest",
        nullable=False,
    )
    op.create_table(
        "scientific_assurance_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_family", sa.String(100), nullable=False),
        sa.Column("extractor_version", sa.String(100), nullable=False),
        sa.Column("produced_by", sa.String(150), nullable=False),
        sa.Column("independence_receipt_digest", sa.String(64)),
        sa.Column("independent_review_digest", sa.String(64)),
        sa.Column("independent_of_representation", sa.Boolean(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("semantic_payload", postgresql.JSONB(), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["scientific_assurance_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_digest"),
        sa.UniqueConstraint(
            "request_id",
            "provider_family",
            "extractor_version",
            name="uq_scientific_assurance_attempt_provider",
        ),
    )
    op.create_index(
        "ix_scientific_assurance_attempts_request_id",
        "scientific_assurance_attempts",
        ["request_id"],
    )
    op.create_index(
        "ix_scientific_assurance_attempts_outcome",
        "scientific_assurance_attempts",
        ["outcome"],
    )
    op.create_table(
        "scientific_assurance_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("representation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_content_digest", sa.String(64), nullable=False),
        sa.Column("source_region_digest", sa.String(64), nullable=False),
        sa.Column("expression_digest", sa.String(64), nullable=False),
        sa.Column("assurance_level", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("deterministic_checks", postgresql.JSONB(), nullable=False),
        sa.Column("attempt_digests", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("claim_boundary", sa.Text(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("issued_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["representation_id"], ["scientific_representations.id"]
        ),
        sa.ForeignKeyConstraint(["request_id"], ["scientific_assurance_requests.id"]),
        sa.ForeignKeyConstraint(
            ["source_object_id"], ["canonical_evidence_objects.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(
        "ix_scientific_assurance_receipts_representation_id",
        "scientific_assurance_receipts",
        ["representation_id"],
    )
    op.create_index(
        "ix_scientific_assurance_receipts_source_object_id",
        "scientific_assurance_receipts",
        ["source_object_id"],
    )
    op.create_index(
        "ix_scientific_assurance_receipts_assurance_level",
        "scientific_assurance_receipts",
        ["assurance_level"],
    )
    op.create_index(
        "ix_scientific_assurance_receipts_status",
        "scientific_assurance_receipts",
        ["status"],
    )


def downgrade() -> None:
    op.drop_column("scientific_calculation_receipts", "assurance_receipt_digest")
    op.drop_table("scientific_assurance_receipts")
    op.drop_table("scientific_assurance_attempts")
    op.drop_table("scientific_assurance_requests")
