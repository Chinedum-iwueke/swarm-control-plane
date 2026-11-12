"""allow canonical hypothesis and research candidate evidence objects

Revision ID: c9f1a4e72b60
Revises: b8e5f0d32c71
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9f1a4e72b60"
down_revision: str | None = "b8e5f0d32c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PREVIOUS_TYPES = (
    "object_type IN ('source','edition','artifact','scientific_object','claim',"
    "'method','assumption','dataset','run','result','review','decision','belief','episode')"
)
_RESEARCH_TYPES = (
    "object_type IN ('source','edition','artifact','scientific_object','claim',"
    "'hypothesis','research_candidate','method','assumption','dataset','run','result',"
    "'review','decision','belief','episode')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_canonical_evidence_object_type",
        "canonical_evidence_objects",
        type_="check",
    )
    op.create_check_constraint(
        "ck_canonical_evidence_object_type",
        "canonical_evidence_objects",
        _RESEARCH_TYPES,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_canonical_evidence_object_type",
        "canonical_evidence_objects",
        type_="check",
    )
    op.create_check_constraint(
        "ck_canonical_evidence_object_type",
        "canonical_evidence_objects",
        _PREVIOUS_TYPES,
    )
