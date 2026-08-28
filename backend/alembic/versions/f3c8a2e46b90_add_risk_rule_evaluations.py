"""add risk rule evaluations

Revision ID: f3c8a2e46b90
Revises: f2b7e1d35a80
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3c8a2e46b90"
down_revision: str | None = "f2b7e1d35a80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_rule_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_key", sa.String(180), nullable=False),
        sa.Column(
            "reference_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "risk_stress_assessment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("rule_pack_digest", sa.String(64), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("receipt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reference_snapshot_id"], ["reference_data_snapshots.id"]
        ),
        sa.ForeignKeyConstraint(
            ["risk_stress_assessment_id"], ["risk_stress_assessments.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_key"),
        sa.UniqueConstraint("receipt_digest"),
    )
    for column in (
        "reference_snapshot_id",
        "risk_stress_assessment_id",
        "rule_pack_digest",
        "decision",
    ):
        op.create_index(
            op.f(f"ix_risk_rule_evaluations_{column}"),
            "risk_rule_evaluations",
            [column],
        )


def downgrade() -> None:
    for column in (
        "decision",
        "rule_pack_digest",
        "risk_stress_assessment_id",
        "reference_snapshot_id",
    ):
        op.drop_index(
            op.f(f"ix_risk_rule_evaluations_{column}"),
            table_name="risk_rule_evaluations",
        )
    op.drop_table("risk_rule_evaluations")
