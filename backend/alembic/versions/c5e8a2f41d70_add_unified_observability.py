"""add unified observability SLO and alert routing

Revision ID: c5e8a2f41d70
Revises: a4c7e1f92b60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8a2f41d70"
down_revision: str | None = "a4c7e1f92b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_slo_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False),
        sa.Column("indicator", sa.String(60), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("objective", postgresql.JSONB(), nullable=False),
        sa.Column("measurement", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("consecutive_breaches", sa.Integer(), nullable=False),
        sa.Column("consecutive_healthy", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_key", "indicator"),
    )
    op.create_index(
        "ix_service_slo_states_service_key", "service_slo_states", ["service_key"]
    )
    op.create_index("ix_service_slo_states_status", "service_slo_states", ["status"])
    op.create_index(
        "ix_service_slo_states_evaluated_at", "service_slo_states", ["evaluated_at"]
    )
    op.create_table(
        "routed_service_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_key", sa.String(240), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False),
        sa.Column("indicator", sa.String(60), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("route", sa.String(80), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("silenced_until", sa.DateTime(timezone=True)),
        sa.Column("recovered_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_key"),
    )
    op.create_index(
        "ix_routed_service_alerts_service_key", "routed_service_alerts", ["service_key"]
    )
    op.create_index(
        "ix_routed_service_alerts_state", "routed_service_alerts", ["state"]
    )
    op.create_table(
        "alert_routing_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["routed_service_alerts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", "sequence"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_alert_routing_events_alert_id", "alert_routing_events", ["alert_id"]
    )


def downgrade() -> None:
    op.drop_table("alert_routing_events")
    op.drop_table("routed_service_alerts")
    op.drop_table("service_slo_states")
