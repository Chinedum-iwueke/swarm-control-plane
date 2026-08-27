"""add model calibration assessments

Revision ID: e6c1a4f83b20
Revises: e5b9d3f72a10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6c1a4f83b20"
down_revision: str | None = "e5b9d3f72a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_calibration_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_key", sa.String(length=180), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dossier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_key", sa.String(length=180), nullable=False),
        sa.Column(
            "specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("specification_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("assessment_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("assessed_by", sa.String(length=150), nullable=False),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dossier_id"], ["evidence_dossiers.id"]),
        sa.ForeignKeyConstraint(["evaluation_id"], ["model_family_evaluations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_digest"),
        sa.UniqueConstraint("assessment_key"),
    )
    op.create_index(
        op.f("ix_model_calibration_assessments_dossier_id"),
        "model_calibration_assessments",
        ["dossier_id"],
    )
    op.create_index(
        op.f("ix_model_calibration_assessments_evaluation_id"),
        "model_calibration_assessments",
        ["evaluation_id"],
    )
    op.create_index(
        op.f("ix_model_calibration_assessments_status"),
        "model_calibration_assessments",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_model_calibration_assessments_status"),
        table_name="model_calibration_assessments",
    )
    op.drop_index(
        op.f("ix_model_calibration_assessments_evaluation_id"),
        table_name="model_calibration_assessments",
    )
    op.drop_index(
        op.f("ix_model_calibration_assessments_dossier_id"),
        table_name="model_calibration_assessments",
    )
    op.drop_table("model_calibration_assessments")
