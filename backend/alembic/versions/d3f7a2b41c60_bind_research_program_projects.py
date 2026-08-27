"""bind research program projects

Revision ID: d3f7a2b41c60
Revises: c2e6f9a31b50
"""

import sqlalchemy as sa
from alembic import op

revision = "d3f7a2b41c60"
down_revision = "c2e6f9a31b50"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("research_programs", sa.Column("project", sa.String(100)))
    op.execute(
        "UPDATE research_programs SET project = 'bulletproof-bt' "
        "WHERE program_key = 'M14-DAILY-SUPERVISED-RESEARCH'"
    )
    op.execute("UPDATE research_programs SET project = 'unbound' WHERE project IS NULL")
    op.alter_column("research_programs", "project", nullable=False)
    op.create_index("ix_research_programs_project", "research_programs", ["project"])


def downgrade():
    op.drop_index("ix_research_programs_project", table_name="research_programs")
    op.drop_column("research_programs", "project")
