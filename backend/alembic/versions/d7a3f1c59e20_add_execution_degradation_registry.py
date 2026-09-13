"""add execution degradation schema registry

Revision ID: d7a3f1c59e20
Revises: c6f2a9d48b70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7a3f1c59e20"
down_revision: str | None = "c6f2a9d48b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_degradation_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("producer", sa.String(length=240), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("specification_digest", sa.String(length=64), nullable=False),
        sa.Column("specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name", "version", name="uq_execution_degradation_schema_name_version"
        ),
        sa.UniqueConstraint("specification_digest"),
    )
    op.create_index(
        op.f("ix_execution_degradation_schema_registry_name"),
        "execution_degradation_schema_registry",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_execution_degradation_schema_registry_specification_digest"),
        "execution_degradation_schema_registry",
        ["specification_digest"],
        unique=True,
    )
    op.create_index(
        op.f("ix_execution_degradation_schema_registry_status"),
        "execution_degradation_schema_registry",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_execution_degradation_schema_registry_status"),
        table_name="execution_degradation_schema_registry",
    )
    op.drop_index(
        op.f("ix_execution_degradation_schema_registry_specification_digest"),
        table_name="execution_degradation_schema_registry",
    )
    op.drop_index(
        op.f("ix_execution_degradation_schema_registry_name"),
        table_name="execution_degradation_schema_registry",
    )
    op.drop_table("execution_degradation_schema_registry")
