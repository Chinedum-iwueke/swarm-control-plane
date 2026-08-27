"""add bounded autonomous research sessions

Revision ID: b1d5e8f20a40
Revises: a0c4d7e96f30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b1d5e8f20a40"
down_revision = "a0c4d7e96f30"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "autonomous_research_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_key", sa.String(180), unique=True, nullable=False),
        sa.Column("project", sa.String(100), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("task_graph_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task_graphs.id"), unique=True, nullable=False),
        sa.Column("task_graph_digest", sa.String(64), nullable=False),
        sa.Column("agenda", postgresql.JSONB(), nullable=False),
        sa.Column("agenda_digest", sa.String(64), nullable=False),
        sa.Column("budget", postgresql.JSONB(), nullable=False),
        sa.Column("budget_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("reconcile_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("no_progress_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_loss_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_progress_digest", sa.String(64), nullable=True),
        sa.Column("terminal_reason", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("closeout", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_autonomous_research_sessions_project", "autonomous_research_sessions", ["project"])
    op.create_index("ix_autonomous_research_sessions_status", "autonomous_research_sessions", ["status"])
    op.create_table(
        "autonomous_research_session_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("autonomous_research_sessions.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64), nullable=True),
        sa.Column("event_digest", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_index("ix_autonomous_research_session_events_session_id", "autonomous_research_session_events", ["session_id"])
    op.create_index("ix_autonomous_research_session_events_event_type", "autonomous_research_session_events", ["event_type"])


def downgrade():
    op.drop_index("ix_autonomous_research_session_events_event_type", table_name="autonomous_research_session_events")
    op.drop_index("ix_autonomous_research_session_events_session_id", table_name="autonomous_research_session_events")
    op.drop_table("autonomous_research_session_events")
    op.drop_index("ix_autonomous_research_sessions_status", table_name="autonomous_research_sessions")
    op.drop_index("ix_autonomous_research_sessions_project", table_name="autonomous_research_sessions")
    op.drop_table("autonomous_research_sessions")
