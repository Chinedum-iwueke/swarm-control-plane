"""add venue identity registry

Revision ID: e4f8b2d05c30
Revises: e3f7a1c94b20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e4f8b2d05c30"
down_revision = "e3f7a1c94b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "venue_identity_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("producer", sa.String(240), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("specification_digest", sa.String(64), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "name", "version", name="uq_venue_identity_name_version"
        ),
        sa.UniqueConstraint(
            "specification_digest", name="uq_venue_identity_specification_digest"
        ),
    )
    op.create_index(
        "ix_venue_identity_registry_name", "venue_identity_registry", ["name"]
    )
    op.create_index(
        "ix_venue_identity_registry_status", "venue_identity_registry", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_venue_identity_registry_status", table_name="venue_identity_registry"
    )
    op.drop_index(
        "ix_venue_identity_registry_name", table_name="venue_identity_registry"
    )
    op.drop_table("venue_identity_registry")
