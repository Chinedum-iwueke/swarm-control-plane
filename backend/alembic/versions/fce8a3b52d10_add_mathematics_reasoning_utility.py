"""add mathematics-aware reasoning utility

Revision ID: fce8a3b52d10
Revises: fbe7d2a41c90
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fce8a3b52d10"
down_revision = "fbe7d2a41c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mathematics_context_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("representation_ids", postgresql.JSONB(), nullable=False),
        sa.Column("context_pack_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "scientific_calculation_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "representation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scientific_representations.id"),
            nullable=False,
        ),
        sa.Column("context_pack_digest", sa.String(64), nullable=False),
        sa.Column("expression_tree", postgresql.JSONB(), nullable=False),
        sa.Column("substitutions", postgresql.JSONB(), nullable=False),
        sa.Column("units", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("representation_digest", sa.String(64), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("executed_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_scientific_calculation_representation",
        "scientific_calculation_receipts",
        ["representation_id"],
    )
    op.create_table(
        "mathematics_capability_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_role", sa.String(100), nullable=False),
        sa.Column("profile_version", sa.String(80), nullable=False),
        sa.Column("corpus_digest", sa.String(64), nullable=False),
        sa.Column("representation_version", sa.String(80), nullable=False),
        sa.Column("demonstrated_tasks", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("record_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "agent_role", "profile_version", name="uq_mathematics_capability_profile"
        ),
    )
    op.create_index(
        "ix_mathematics_capability_agent_role",
        "mathematics_capability_profiles",
        ["agent_role"],
    )
    op.create_index(
        "ix_mathematics_capability_status",
        "mathematics_capability_profiles",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("mathematics_capability_profiles")
    op.drop_table("scientific_calculation_receipts")
    op.drop_table("mathematics_context_packs")
