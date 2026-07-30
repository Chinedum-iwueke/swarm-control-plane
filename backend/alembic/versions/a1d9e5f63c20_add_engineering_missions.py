"""Add engineering missions and task dependencies

Revision ID: a1d9e5f63c20
Revises: f4c8d1a72b60
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1d9e5f63c20"
down_revision: str | None = "f4c8d1a72b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "engineering_missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("milestone_id", sa.String(100), nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("approved_by", sa.String(150), nullable=False),
        sa.Column("approval_reference", sa.String(200), nullable=False),
        sa.Column("approval_signature", sa.String(64), nullable=False),
        sa.Column("max_tasks", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("milestone_id"),
    )
    op.create_index(
        "ix_engineering_missions_project", "engineering_missions", ["project"]
    )
    op.create_index(
        "ix_engineering_missions_status", "engineering_missions", ["status"]
    )
    op.create_table(
        "mission_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["mission_id"], ["engineering_missions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mission_events_mission_id", "mission_events", ["mission_id"])
    op.create_index("ix_mission_events_event_type", "mission_events", ["event_type"])
    op.execute(
        """
        CREATE TRIGGER mission_events_append_only
        BEFORE UPDATE OR DELETE ON mission_events
        FOR EACH ROW EXECUTE FUNCTION prevent_governance_evidence_mutation();
        """
    )
    op.add_column(
        "tasks",
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tasks", sa.Column("milestone_step_id", sa.String(100), nullable=True)
    )
    op.create_foreign_key(
        "fk_tasks_mission_id",
        "tasks",
        "engineering_missions",
        ["mission_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_mission_id", "tasks", ["mission_id"])
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "depends_on_task_id"),
    )
    op.create_index("ix_task_dependencies_task_id", "task_dependencies", ["task_id"])
    op.create_index(
        "ix_task_dependencies_depends_on_task_id",
        "task_dependencies",
        ["depends_on_task_id"],
    )


def downgrade() -> None:
    op.drop_table("task_dependencies")
    op.drop_index("ix_tasks_mission_id", table_name="tasks")
    op.drop_constraint("fk_tasks_mission_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "milestone_step_id")
    op.drop_column("tasks", "mission_id")
    op.drop_table("mission_events")
    op.drop_table("engineering_missions")
