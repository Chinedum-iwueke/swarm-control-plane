"""add prompt policy and model output security registry

Revision ID: c4f8a2d61e90
Revises: b3e7a1c52d90
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f8a2d61e90"
down_revision: str | None = "b3e7a1c52d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_policy_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bundle_key", sa.String(100), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("model_binding", postgresql.JSONB(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False),
        sa.Column("trust_labels", postgresql.JSONB(), nullable=False),
        sa.Column("allowed_tools", postgresql.JSONB(), nullable=False),
        sa.Column("allowed_data_classes", postgresql.JSONB(), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("bundle_key", "version"),
    )
    op.create_index(
        "ix_prompt_policy_bundles_bundle_key", "prompt_policy_bundles", ["bundle_key"]
    )
    op.create_index(
        "ix_prompt_policy_bundles_status", "prompt_policy_bundles", ["status"]
    )
    op.create_table(
        "prompt_policy_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bundle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_policy_bundles.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("fixture_digest", sa.String(64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("violations", postgresql.JSONB(), nullable=False),
        sa.Column("receipt", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluated_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("bundle_id", "fixture_digest"),
    )
    op.create_index(
        "ix_prompt_policy_evaluations_bundle_id",
        "prompt_policy_evaluations",
        ["bundle_id"],
    )
    op.create_index(
        "ix_prompt_policy_evaluations_category",
        "prompt_policy_evaluations",
        ["category"],
    )
    op.create_table(
        "prompt_policy_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "bundle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prompt_policy_bundles.id"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("previous_digest", sa.String(64)),
        sa.Column("event_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("bundle_id", "sequence"),
    )
    op.create_index(
        "ix_prompt_policy_events_bundle_id", "prompt_policy_events", ["bundle_id"]
    )
    op.create_index(
        "ix_prompt_policy_events_event_type", "prompt_policy_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_table("prompt_policy_events")
    op.drop_table("prompt_policy_evaluations")
    op.drop_table("prompt_policy_bundles")
