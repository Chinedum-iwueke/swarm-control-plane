"""add orthogonal institutional lifecycles

Revision ID: f7c2a9d41e80
Revises: e6b1a4d82f90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7c2a9d41e80"
down_revision: str | None = "e6b1a4d82f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "institutional_lifecycle_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("dimension", sa.String(30), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("last_event_digest", sa.String(64)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("subject_type", "subject_id", "dimension"),
    )
    for column in ("subject_type", "subject_id", "dimension", "state"):
        op.create_index(
            f"ix_institutional_lifecycle_projections_{column}",
            "institutional_lifecycle_projections",
            [column],
        )
    op.create_table(
        "institutional_lifecycle_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "projection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutional_lifecycle_projections.id"),
            nullable=False,
        ),
        sa.Column(
            "command_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True
        ),
        sa.Column("dimension", sa.String(30), nullable=False),
        sa.Column("command", sa.String(80), nullable=False),
        sa.Column("prior_state", sa.String(40), nullable=False),
        sa.Column("resulting_state", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column(
            "authority_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("authority_decision_records.id"),
            nullable=False,
        ),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("prior_event_digest", sa.String(64)),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in ("projection_id", "dimension", "actor"):
        op.create_index(
            f"ix_institutional_lifecycle_events_{column}",
            "institutional_lifecycle_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("institutional_lifecycle_events")
    op.drop_table("institutional_lifecycle_projections")
