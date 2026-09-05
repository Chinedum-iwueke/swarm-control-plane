"""add scientific fidelity registry

Revision ID: fae4c6b93d20
Revises: f9d3e5b82a10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fae4c6b93d20"
down_revision = "f9d3e5b82a10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("scientific_representations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canonical_evidence_objects.id"), nullable=False),
        sa.Column("representation_version", sa.String(80), nullable=False), sa.Column("scientific_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("normalized_content", sa.Text(), nullable=False),
        sa.Column("semantic_payload", postgresql.JSONB(), nullable=False), sa.Column("parser_outputs", postgresql.JSONB(), nullable=False),
        sa.Column("uncertainties", postgresql.JSONB(), nullable=False), sa.Column("source_region_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True), sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source_object_id", "representation_version", name="uq_scientific_representation_source_version"))
    op.create_index("ix_scientific_representations_source", "scientific_representations", ["source_object_id"])
    op.create_index("ix_scientific_representations_status", "scientific_representations", ["status"])
    op.create_table("scientific_fidelity_manifests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("representation_version", sa.String(80), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("thresholds", postgresql.JSONB(), nullable=False), sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False), sa.Column("representation_digests", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True), sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_scientific_fidelity_manifest_corpus", "scientific_fidelity_manifests", ["corpus_digest"])


def downgrade() -> None:
    op.drop_table("scientific_fidelity_manifests")
    op.drop_table("scientific_representations")
