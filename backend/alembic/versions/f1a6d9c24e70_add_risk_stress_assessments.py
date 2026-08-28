"""add risk stress assessments

Revision ID: f1a6d9c24e70
Revises: e8c3b6a05d40
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a6d9c24e70"
down_revision: str | None = "e8c3b6a05d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_stress_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_key", sa.String(180), nullable=False),
        sa.Column("candidate_digest", sa.String(64), nullable=False),
        sa.Column("scenario_pack_digest", sa.String(64), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dossier", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dossier_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("assessed_by", sa.String(150), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_key"),
        sa.UniqueConstraint("dossier_digest"),
    )
    op.create_index(op.f("ix_risk_stress_assessments_candidate_digest"), "risk_stress_assessments", ["candidate_digest"])
    op.create_index(op.f("ix_risk_stress_assessments_decision"), "risk_stress_assessments", ["decision"])


def downgrade() -> None:
    op.drop_index(op.f("ix_risk_stress_assessments_decision"), table_name="risk_stress_assessments")
    op.drop_index(op.f("ix_risk_stress_assessments_candidate_digest"), table_name="risk_stress_assessments")
    op.drop_table("risk_stress_assessments")
