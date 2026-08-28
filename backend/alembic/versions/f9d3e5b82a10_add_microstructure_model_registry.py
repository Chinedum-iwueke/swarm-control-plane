"""add microstructure model registry

Revision ID: f9d3e5b82a10
Revises: f8c2d4a71e90
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f9d3e5b82a10"
down_revision = "f8c2d4a71e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "microstructure_model_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_microstructure_model_name_version"),
        sa.UniqueConstraint("specification_digest", name="uq_microstructure_model_digest"),
    )
    op.create_index("ix_microstructure_model_status", "microstructure_model_registry", ["status"])


def downgrade() -> None:
    op.drop_index("ix_microstructure_model_status", table_name="microstructure_model_registry")
    op.drop_table("microstructure_model_registry")
