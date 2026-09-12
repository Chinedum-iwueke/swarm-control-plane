"""add candidate admission schema registry

Revision ID: d1a6b4e83c90
Revises: c9f5a1d72b80
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d1a6b4e83c90"
down_revision = "c9f5a1d72b80"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_admission_schema_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name", "version", name="uq_candidate_admission_schema_name_version"
        ),
        sa.UniqueConstraint("specification_digest"),
    )
    op.create_index(
        "ix_candidate_admission_schema_registry_name",
        "candidate_admission_schema_registry",
        ["name"],
    )
    op.create_index(
        "ix_candidate_admission_schema_registry_specification_digest",
        "candidate_admission_schema_registry",
        ["specification_digest"],
    )
    op.create_index(
        "ix_candidate_admission_schema_registry_status",
        "candidate_admission_schema_registry",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_candidate_admission_schema_registry_status",
        table_name="candidate_admission_schema_registry",
    )
    op.drop_index(
        "ix_candidate_admission_schema_registry_specification_digest",
        table_name="candidate_admission_schema_registry",
    )
    op.drop_index(
        "ix_candidate_admission_schema_registry_name",
        table_name="candidate_admission_schema_registry",
    )
    op.drop_table("candidate_admission_schema_registry")
