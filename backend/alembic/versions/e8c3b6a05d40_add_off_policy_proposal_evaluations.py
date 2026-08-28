"""add off policy proposal evaluations

Revision ID: e8c3b6a05d40
Revises: e7d2b5a94c30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8c3b6a05d40"
down_revision: str | None = "e7d2b5a94c30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "off_policy_proposal_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_key", sa.String(length=180), nullable=False),
        sa.Column("dataset_contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selection_audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "calibration_assessment_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposal_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "evaluation", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("evaluation_digest", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("evaluated_by", sa.String(length=150), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["calibration_assessment_id"], ["model_calibration_assessments.id"]
        ),
        sa.ForeignKeyConstraint(
            ["dataset_contract_id"], ["offline_rl_dataset_contracts.id"]
        ),
        sa.ForeignKeyConstraint(["selection_audit_id"], ["selection_bias_audits.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_digest"),
        sa.UniqueConstraint("evaluation_key"),
    )
    for column in (
        "calibration_assessment_id",
        "dataset_contract_id",
        "selection_audit_id",
        "decision",
    ):
        op.create_index(
            op.f(f"ix_off_policy_proposal_evaluations_{column}"),
            "off_policy_proposal_evaluations",
            [column],
        )


def downgrade() -> None:
    for column in (
        "decision",
        "selection_audit_id",
        "dataset_contract_id",
        "calibration_assessment_id",
    ):
        op.drop_index(
            op.f(f"ix_off_policy_proposal_evaluations_{column}"),
            table_name="off_policy_proposal_evaluations",
        )
    op.drop_table("off_policy_proposal_evaluations")
