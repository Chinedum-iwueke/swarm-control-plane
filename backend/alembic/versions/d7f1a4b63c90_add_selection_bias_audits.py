"""add selection bias audits

Revision ID: d7f1a4b63c90
Revises: c6e9f3a52b80
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7f1a4b63c90"
down_revision: str | None = "c6e9f3a52b80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "selection_bias_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("audit_key", sa.String(180), nullable=False),
        sa.Column(
            "mechanism_evaluation_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("ledger", postgresql.JSONB(), nullable=False),
        sa.Column("ledger_digest", sa.String(64), nullable=False),
        sa.Column("audit", postgresql.JSONB(), nullable=False),
        sa.Column("conclusion", sa.String(40), nullable=False),
        sa.Column("audit_digest", sa.String(64), nullable=False),
        sa.Column("supersedes_audit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("audited_by", sa.String(150), nullable=False),
        sa.Column(
            "audited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mechanism_evaluation_id"], ["mechanism_evaluations.id"]
        ),
        sa.ForeignKeyConstraint(["supersedes_audit_id"], ["selection_bias_audits.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_key"),
        sa.UniqueConstraint("audit_digest"),
    )
    op.create_index(
        "ix_selection_bias_audits_ledger_digest",
        "selection_bias_audits",
        ["ledger_digest"],
    )
    op.create_index(
        "ix_selection_bias_audits_mechanism_evaluation_id",
        "selection_bias_audits",
        ["mechanism_evaluation_id"],
    )
    op.create_index(
        "ix_selection_bias_audits_conclusion",
        "selection_bias_audits",
        ["conclusion"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_selection_bias_audits_ledger_digest", table_name="selection_bias_audits"
    )
    op.drop_index(
        "ix_selection_bias_audits_conclusion", table_name="selection_bias_audits"
    )
    op.drop_index(
        "ix_selection_bias_audits_mechanism_evaluation_id",
        table_name="selection_bias_audits",
    )
    op.drop_table("selection_bias_audits")
