"""add RI-008 knowledge graph and cognitive tool services

Revision ID: 6e8a1c4d9b20
Revises: 4d8f1b2c6a70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6e8a1c4d9b20"
down_revision: str | None = "4d8f1b2c6a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "canonical_evidence_edges",
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_evidence_edges",
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "canonical_evidence_edges",
        sa.Column("provenance_object_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "canonical_evidence_edges",
        sa.Column(
            "access_class",
            sa.String(30),
            server_default="internal",
            nullable=False,
        ),
    )
    op.add_column(
        "canonical_evidence_edges",
        sa.Column("record_digest", sa.String(64), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_edge_provenance",
        "canonical_evidence_edges",
        "canonical_evidence_objects",
        ["provenance_object_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_evidence_edge_record_digest",
        "canonical_evidence_edges",
        ["record_digest"],
    )

    op.create_table(
        "evidence_graph_projection_states",
        sa.Column("projection_name", sa.String(100), primary_key=True),
        sa.Column("projection_version", sa.String(100), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column(
            "built_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "evidence_graph_projection_nodes",
        sa.Column("object_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("projection_version", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["object_id"], ["canonical_evidence_objects.id"], ondelete="CASCADE"
        ),
    )
    for column in ("object_type", "project", "access_class"):
        op.create_index(
            f"ix_evidence_graph_node_{column}",
            "evidence_graph_projection_nodes",
            [column],
        )
    op.create_table(
        "evidence_graph_projection_edges",
        sa.Column("edge_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicate", sa.String(100), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provenance_object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("projection_version", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["edge_id"], ["canonical_evidence_edges.id"], ondelete="CASCADE"
        ),
    )
    for column in ("subject_id", "predicate", "object_id"):
        op.create_index(
            f"ix_evidence_graph_edge_{column}",
            "evidence_graph_projection_edges",
            [column],
        )
    op.create_table(
        "cognitive_tool_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(100), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("output_digest", sa.String(64), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("context_pack_digest", sa.String(64), nullable=True),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_cognitive_tool_receipt_tool",
        "cognitive_tool_receipts",
        ["tool_name"],
    )


def downgrade() -> None:
    op.drop_table("cognitive_tool_receipts")
    op.drop_table("evidence_graph_projection_edges")
    op.drop_table("evidence_graph_projection_nodes")
    op.drop_table("evidence_graph_projection_states")
    op.drop_constraint(
        "uq_evidence_edge_record_digest", "canonical_evidence_edges", type_="unique"
    )
    op.drop_constraint(
        "fk_evidence_edge_provenance", "canonical_evidence_edges", type_="foreignkey"
    )
    op.drop_column("canonical_evidence_edges", "record_digest")
    op.drop_column("canonical_evidence_edges", "access_class")
    op.drop_column("canonical_evidence_edges", "provenance_object_id")
    op.drop_column("canonical_evidence_edges", "valid_until")
    op.drop_column("canonical_evidence_edges", "valid_from")
