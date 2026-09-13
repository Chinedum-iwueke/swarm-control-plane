"""add execution telemetry registry

Revision ID: e8b4c2d60f31
Revises: d7a3f1c59e20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8b4c2d60f31"
down_revision: str | None = "d7a3f1c59e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_telemetry_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column(
            "specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name", "version", name="uq_execution_telemetry_schema_name_version"
        ),
        sa.UniqueConstraint("specification_digest"),
    )
    op.create_index(
        "ix_execution_telemetry_schema_registry_name",
        "execution_telemetry_schema_registry",
        ["name"],
    )
    op.create_index(
        "ix_execution_telemetry_schema_registry_status",
        "execution_telemetry_schema_registry",
        ["status"],
    )
    op.create_index(
        "ix_execution_telemetry_schema_registry_specification_digest",
        "execution_telemetry_schema_registry",
        ["specification_digest"],
    )
    op.create_table(
        "execution_telemetry_replays",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("projection_digest", sa.String(64), nullable=False),
        sa.Column("schema_digest", sa.String(64), nullable=False),
        sa.Column("venue", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("account_pseudonym", sa.String(120), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "projection", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_digest"),
        sa.UniqueConstraint("projection_digest"),
    )
    for name in (
        "receipt_digest",
        "projection_digest",
        "schema_digest",
        "venue",
        "environment",
        "account_pseudonym",
        "observed_at",
        "status",
    ):
        op.create_index(
            f"ix_execution_telemetry_replays_{name}",
            "execution_telemetry_replays",
            [name],
        )


def downgrade() -> None:
    op.drop_table("execution_telemetry_replays")
    op.drop_table("execution_telemetry_schema_registry")
