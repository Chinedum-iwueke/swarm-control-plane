"""add alpha discovery representation stage

Revision ID: d3b9f5a72e01
Revises: c2a8e4f61d90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3b9f5a72e01"
down_revision: str | None = "c2a8e4f61d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alpha_discovery_cycles",
        sa.Column("representation_task_id", postgresql.UUID(as_uuid=True)),
    )
    op.add_column(
        "alpha_discovery_cycles",
        sa.Column(
            "representation_brief",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_alpha_discovery_cycles_representation_task_id_tasks",
        "alpha_discovery_cycles",
        "tasks",
        ["representation_task_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_alpha_discovery_cycles_representation_task_id_tasks",
        "alpha_discovery_cycles",
        type_="foreignkey",
    )
    op.drop_column("alpha_discovery_cycles", "representation_brief")
    op.drop_column("alpha_discovery_cycles", "representation_task_id")
