"""allow canonical result evidence objects

Revision ID: f1a6d3c84b20
Revises: e8b1c4d72f90
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a6d3c84b20"
down_revision: str | None = "e8b1c4d72f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_WITHOUT_RESULT = (
    "object_type IN ('source','edition','artifact','scientific_object','claim',"
    "'method','assumption','dataset','run','review','decision','belief','episode')"
)
_WITH_RESULT = (
    "object_type IN ('source','edition','artifact','scientific_object','claim',"
    "'method','assumption','dataset','run','result','review','decision','belief','episode')"
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
        _WITH_RESULT,
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
        _WITHOUT_RESULT,
    )
