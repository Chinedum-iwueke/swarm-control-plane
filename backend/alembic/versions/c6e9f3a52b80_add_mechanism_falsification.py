"""add mechanism plans and falsification evaluations

Revision ID: c6e9f3a52b80
Revises: b5d8e2f41a70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c6e9f3a52b80"
down_revision: str | None = "b5d8e2f41a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mechanism_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_key", sa.String(180), nullable=False),
        sa.Column("discovery_map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["discovery_map_id"], ["discovery_maps.id"]),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["research_hypotheses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_key"),
        sa.UniqueConstraint("plan_digest"),
    )
    op.create_index(
        "ix_mechanism_plans_discovery_map_id", "mechanism_plans", ["discovery_map_id"]
    )
    op.create_index(
        "ix_mechanism_plans_hypothesis_id", "mechanism_plans", ["hypothesis_id"]
    )
    op.create_table(
        "mechanism_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_key", sa.String(180), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation", postgresql.JSONB(), nullable=False),
        sa.Column("conclusion", sa.String(30), nullable=False),
        sa.Column("evaluation_digest", sa.String(64), nullable=False),
        sa.Column(
            "supersedes_evaluation_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["mechanism_plans.id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_evaluation_id"], ["mechanism_evaluations.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evaluation_key"),
        sa.UniqueConstraint("evaluation_digest"),
    )
    op.create_index(
        "ix_mechanism_evaluations_plan_id", "mechanism_evaluations", ["plan_id"]
    )
    op.create_index(
        "ix_mechanism_evaluations_conclusion", "mechanism_evaluations", ["conclusion"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mechanism_evaluations_conclusion", table_name="mechanism_evaluations"
    )
    op.drop_index(
        "ix_mechanism_evaluations_plan_id", table_name="mechanism_evaluations"
    )
    op.drop_table("mechanism_evaluations")
    op.drop_index("ix_mechanism_plans_hypothesis_id", table_name="mechanism_plans")
    op.drop_index("ix_mechanism_plans_discovery_map_id", table_name="mechanism_plans")
    op.drop_table("mechanism_plans")
