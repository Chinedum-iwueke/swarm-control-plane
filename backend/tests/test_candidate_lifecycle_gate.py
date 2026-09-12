from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.services.candidate_lifecycle_gate import require_risk004_evidence
from fastapi import HTTPException


def record(**updates):
    result = {
        "candidate_digest": "a" * 64,
        "requested_action": "admit",
        "eligible_for_authority_review": True,
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    result.update(updates)
    return SimpleNamespace(receipt={"result": result})


def db_with(*records):
    db = MagicMock()
    db.scalars.return_value.all.return_value = list(records)
    return db


def test_exact_fresh_receipt_is_required():
    require_risk004_evidence(
        db_with(record()),
        subject_type="portfolio-candidate",
        subject_digest="a" * 64,
        requested_action="admit",
        evidence=["b" * 64],
    )
    for bad in (
        record(candidate_digest="c" * 64),
        record(eligible_for_authority_review=False),
        record(expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()),
    ):
        with pytest.raises(HTTPException, match="fresh, exact"):
            require_risk004_evidence(
                db_with(bad),
                subject_type="portfolio-candidate",
                subject_digest="a" * 64,
                requested_action="admit",
                evidence=["b" * 64],
            )


def test_non_candidate_subject_is_unchanged():
    require_risk004_evidence(
        MagicMock(),
        subject_type="evidence",
        subject_digest="a" * 64,
        requested_action="admit",
        evidence=[],
    )
