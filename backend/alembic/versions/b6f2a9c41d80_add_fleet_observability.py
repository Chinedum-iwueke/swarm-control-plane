"""add fleet observability and incident ledger

Revision ID: b6f2a9c41d80
Revises: a4e7c9d21f60
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b6f2a9c41d80"
down_revision: str | None = "a4e7c9d21f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "machine_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("machine", sa.String(100), nullable=False),
        sa.Column("sample_id", sa.String(100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("service_health", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column("retention_class", sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine", "sample_id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_machine_observations_machine", "machine_observations", ["machine"]
    )
    op.create_index(
        "ix_machine_observations_observed_at", "machine_observations", ["observed_at"]
    )
    op.create_table(
        "fleet_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("machine", sa.String(100), nullable=False),
        sa.Column("signal", sa.String(60), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("consecutive_breaches", sa.Integer(), nullable=False),
        sa.Column("consecutive_healthy", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovered_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("silenced_until", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fleet_incidents_machine", "fleet_incidents", ["machine"])
    op.create_index("ix_fleet_incidents_signal", "fleet_incidents", ["signal"])
    op.create_index("ix_fleet_incidents_state", "fleet_incidents", ["state"])
    op.create_table(
        "fleet_incident_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("prior_state", sa.String(30)),
        sa.Column("resulting_state", sa.String(30), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["fleet_incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_digest"),
    )
    op.create_index(
        "ix_fleet_incident_events_incident_id", "fleet_incident_events", ["incident_id"]
    )


def downgrade() -> None:
    op.drop_table("fleet_incident_events")
    op.drop_table("fleet_incidents")
    op.drop_table("machine_observations")
