"""add founder alpha idea queue

Revision ID: b1e7f9a03c62
Revises: a0d6e8f92b51
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1e7f9a03c62"
down_revision: str | None = "a0d6e8f92b51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alpha_founder_research_ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mandate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True)),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("submitted_by", sa.String(150), nullable=False),
        sa.Column("idea", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False),
        sa.Column("idea_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), server_default="queued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mandate_id"], ["alpha_research_mandates.id"]),
        sa.ForeignKeyConstraint(["cycle_id"], ["alpha_discovery_cycles.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["founder_conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idea_digest"),
    )
    for column in ("mandate_id", "cycle_id", "conversation_id", "status"):
        op.create_index(f"ix_alpha_founder_research_ideas_{column}", "alpha_founder_research_ideas", [column])


def downgrade() -> None:
    op.drop_table("alpha_founder_research_ideas")
