"""add contradiction belief and dossier services

Revision ID: f9b2d5e74c10
Revises: e7a1c4d83b20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9b2d5e74c10"
down_revision: str | None = "e7a1c4d83b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_opposition_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("subject_claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opposing_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opposition_type", sa.String(40), nullable=False),
        sa.Column("comparability", postgresql.JSONB(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "opposition_type IN ('direct_contradiction','boundary_failure',"
            "'replication_failure','method_critique','alternative_explanation',"
            "'operational_contradiction')",
            name="ck_evidence_opposition_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','reviewed','resolved','unresolved')",
            name="ck_evidence_opposition_status",
        ),
        sa.ForeignKeyConstraint(
            ["subject_claim_id"], ["canonical_evidence_objects.id"]
        ),
        sa.ForeignKeyConstraint(
            ["opposing_object_id"], ["canonical_evidence_objects.id"]
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["evidence_opposition_records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
        sa.UniqueConstraint(
            "subject_claim_id", "opposing_object_id", "record_digest"
        ),
    )
    for suffix, columns in (
        ("project", ["project"]),
        ("type", ["opposition_type"]),
        ("status", ["status"]),
    ):
        op.create_index(
            f"ix_evidence_opposition_{suffix}",
            "evidence_opposition_records",
            columns,
        )
    op.create_table(
        "evidence_outcome_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("evidence_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outcome_kind", sa.String(30), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("uncertainty", postgresql.JSONB(), nullable=False),
        sa.Column(
            "failure_mechanisms", postgresql.ARRAY(sa.String(200)), nullable=False
        ),
        sa.Column(
            "affected_claim_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("recorded_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome_kind IN ('valid_negative','invalid_attempt')",
            name="ck_evidence_outcome_kind",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_object_id"], ["canonical_evidence_objects.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_evidence_outcome_project", "evidence_outcome_records", ["project"]
    )
    op.create_index(
        "ix_evidence_outcome_kind", "evidence_outcome_records", ["outcome_kind"]
    )
    op.create_table(
        "evidence_dossiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_key", sa.String(150), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("access_class", sa.String(30), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("decision_context", sa.Text(), nullable=False),
        sa.Column("evidence_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dossier", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("compiler_version", sa.String(100), nullable=False),
        sa.Column("compiled_by", sa.String(100), nullable=False),
        sa.Column(
            "frozen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "access_class IN ('public','internal','restricted','protected')",
            name="ck_evidence_dossier_access",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dossier_key", "version"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_evidence_dossier_key", "evidence_dossiers", ["dossier_key"]
    )
    op.create_index(
        "ix_evidence_dossier_project", "evidence_dossiers", ["project"]
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_dossier_project", table_name="evidence_dossiers")
    op.drop_index("ix_evidence_dossier_key", table_name="evidence_dossiers")
    op.drop_table("evidence_dossiers")
    op.drop_index("ix_evidence_outcome_kind", table_name="evidence_outcome_records")
    op.drop_index("ix_evidence_outcome_project", table_name="evidence_outcome_records")
    op.drop_table("evidence_outcome_records")
    op.drop_index("ix_evidence_opposition_status", table_name="evidence_opposition_records")
    op.drop_index("ix_evidence_opposition_type", table_name="evidence_opposition_records")
    op.drop_index("ix_evidence_opposition_project", table_name="evidence_opposition_records")
    op.drop_table("evidence_opposition_records")
