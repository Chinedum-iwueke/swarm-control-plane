"""add typed task graphs and bounded cancellation

Revision ID: b3e7a1c52d90
Revises: a2d6f9c41e80
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e7a1c52d90"
down_revision: str | None = "a2d6f9c41e80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_key", sa.String(100), nullable=False, unique=True),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("max_nodes", sa.Integer(), nullable=False),
        sa.Column("max_total_attempts", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("max_parallelism", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("terminal_reason", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("deadline_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_task_graphs_project", "task_graphs", ["project"])
    op.create_index("ix_task_graphs_status", "task_graphs", ["status"])
    op.create_index("ix_task_graphs_deadline_at", "task_graphs", ["deadline_at"])
    op.create_table(
        "task_graph_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_graphs.id"), nullable=False),
        sa.Column("node_key", sa.String(100), nullable=False),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("node_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("depends_on", postgresql.JSONB(), nullable=False),
        sa.Column("input_type", sa.String(100), nullable=False),
        sa.Column("output_type", sa.String(100), nullable=False),
        sa.Column("task_spec", postgresql.JSONB(), nullable=False),
        sa.Column("stop_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("compensation", postgresql.JSONB(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("graph_id", "node_key"),
    )
    op.create_index("ix_task_graph_nodes_graph_id", "task_graph_nodes", ["graph_id"])
    op.create_index("ix_task_graph_nodes_task_id", "task_graph_nodes", ["task_id"])
    op.create_index("ix_task_graph_nodes_status", "task_graph_nodes", ["status"])
    op.add_column("tasks", sa.Column("task_graph_node_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key("fk_tasks_task_graph_node", "tasks", "task_graph_nodes", ["task_graph_node_id"], ["id"])
    op.create_index("ix_tasks_task_graph_node_id", "tasks", ["task_graph_node_id"])
    op.add_column("tasks", sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
    op.add_column("tasks", sa.Column("cancel_reason", sa.Text()))
    op.create_table(
        "task_graph_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_graphs.id"), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_graph_nodes.id")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("message_type", sa.String(100), nullable=False),
        sa.Column("sender", sa.String(100), nullable=False),
        sa.Column("recipient", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("graph_id", "sequence"),
    )
    op.create_index("ix_task_graph_messages_graph_id", "task_graph_messages", ["graph_id"])
    op.create_index("ix_task_graph_messages_node_id", "task_graph_messages", ["node_id"])
    op.create_table(
        "task_graph_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_graphs.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64)),
        sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("graph_id", "sequence"),
    )
    op.create_index("ix_task_graph_events_graph_id", "task_graph_events", ["graph_id"])
    op.create_index("ix_task_graph_events_event_type", "task_graph_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("task_graph_events")
    op.drop_table("task_graph_messages")
    op.drop_index("ix_tasks_task_graph_node_id", table_name="tasks")
    op.drop_constraint("fk_tasks_task_graph_node", "tasks", type_="foreignkey")
    op.drop_column("tasks", "cancel_reason")
    op.drop_column("tasks", "cancel_requested_at")
    op.drop_column("tasks", "task_graph_node_id")
    op.drop_table("task_graph_nodes")
    op.drop_table("task_graphs")
