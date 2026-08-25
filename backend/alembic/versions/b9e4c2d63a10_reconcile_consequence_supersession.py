"""reconcile lifecycle consequence supersession

Revision ID: b9e4c2d63a10
Revises: a8d3f1c52b90
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b9e4c2d63a10"
down_revision: str | None = "a8d3f1c52b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "lifecycle_consequences_status_check", "lifecycle_consequences", type_="check"
    )
    op.create_check_constraint(
        "lifecycle_consequences_status_check",
        "lifecycle_consequences",
        "status IN ('active','reversed','expired','reversal','superseded')",
    )
    op.execute("""
        WITH successors AS (
          SELECT DISTINCT ON (prior.id) prior.id AS prior_id, later.id AS later_id,
                 later.resulting_state = prior.rollback_state AS is_reversal
          FROM lifecycle_consequences prior
          JOIN institutional_lifecycle_events pe ON pe.id = prior.event_id
          JOIN lifecycle_consequences later ON later.created_at > prior.created_at
          JOIN institutional_lifecycle_events le ON le.id = later.event_id
               AND le.projection_id = pe.projection_id
          WHERE prior.status = 'active' AND later.prior_state = prior.resulting_state
          ORDER BY prior.id, later.created_at
        )
        UPDATE lifecycle_consequences prior
        SET status = 'superseded', reversed_by_id = successors.later_id
        FROM successors WHERE prior.id = successors.prior_id
    """)
    op.execute("""
        UPDATE lifecycle_consequences later
        SET reversal_of_id = prior.id
        FROM lifecycle_consequences prior
        WHERE prior.reversed_by_id = later.id
          AND later.resulting_state = prior.rollback_state
          AND later.reversal_of_id IS NULL
    """)


def downgrade() -> None:
    op.execute(
        "UPDATE lifecycle_consequences SET status = 'reversed' WHERE status = 'superseded'"
    )
    op.drop_constraint(
        "lifecycle_consequences_status_check", "lifecycle_consequences", type_="check"
    )
    op.create_check_constraint(
        "lifecycle_consequences_status_check",
        "lifecycle_consequences",
        "status IN ('active','reversed','expired','reversal')",
    )
