"""add independent evaluator routing and anti-collusion evidence

Revision ID: d5a9c3e72f10
Revises: c4f8a2d61e90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5a9c3e72f10"
down_revision: str | None = "c4f8a2d61e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evaluator_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id"),
            nullable=False,
        ),
        sa.Column("profile_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("review_kinds", postgresql.JSONB(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("machine", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_family", sa.String(120), nullable=False),
        sa.Column("runtime", sa.String(120), nullable=False),
        sa.Column("context_group", sa.String(120), nullable=False),
        sa.Column(
            "package_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("role_packages.id"),
            nullable=False,
        ),
        sa.Column("package_digest", sa.String(64), nullable=False),
        sa.Column("attestation", postgresql.JSONB(), nullable=False),
        sa.Column("profile_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("registered_by", sa.String(150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("agent_id", "profile_version"),
    )
    op.create_index(
        "ix_evaluator_profiles_agent_id", "evaluator_profiles", ["agent_id"]
    )
    op.create_index("ix_evaluator_profiles_status", "evaluator_profiles", ["status"])
    op.create_table(
        "evaluation_routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(60), nullable=False),
        sa.Column("subject_id", sa.String(150), nullable=False),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("producer", postgresql.JSONB(), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("route_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("requested_by", sa.String(150), nullable=False),
        sa.Column("blocked_reason", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_evaluation_routes_subject_type", "evaluation_routes", ["subject_type"]
    )
    op.create_index(
        "ix_evaluation_routes_subject_id", "evaluation_routes", ["subject_id"]
    )
    op.create_index("ix_evaluation_routes_status", "evaluation_routes", ["status"])
    op.create_table(
        "evaluator_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_routes.id"),
            nullable=False,
        ),
        sa.Column(
            "evaluator_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluator_profiles.id"),
            nullable=False,
        ),
        sa.Column("review_kind", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("correlation_report", postgresql.JSONB(), nullable=False),
        sa.Column("assignment_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("review_id", sa.String(150)),
        sa.Column("review_digest", sa.String(64)),
        sa.Column("completed_by", sa.String(150)),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("route_id", "review_kind"),
        sa.UniqueConstraint("route_id", "evaluator_profile_id"),
    )
    op.create_index(
        "ix_evaluator_assignments_route_id", "evaluator_assignments", ["route_id"]
    )
    op.create_index(
        "ix_evaluator_assignments_evaluator_profile_id",
        "evaluator_assignments",
        ["evaluator_profile_id"],
    )
    op.create_index(
        "ix_evaluator_assignments_status", "evaluator_assignments", ["status"]
    )
    op.create_table(
        "evaluation_route_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_routes.id"),
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
        sa.UniqueConstraint("route_id", "sequence"),
    )
    op.create_index(
        "ix_evaluation_route_events_route_id", "evaluation_route_events", ["route_id"]
    )
    op.create_index(
        "ix_evaluation_route_events_event_type",
        "evaluation_route_events",
        ["event_type"],
    )
    op.create_table(
        "evaluation_independence_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "route_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_routes.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("assertion", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_by", sa.String(150), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("evaluation_independence_receipts")
    op.drop_table("evaluation_route_events")
    op.drop_table("evaluator_assignments")
    op.drop_table("evaluation_routes")
    op.drop_table("evaluator_profiles")
