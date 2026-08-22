from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from app.services.blocked_artifact_register import blocked_artifact_register


def _job(*, status: str = "rejected") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        project="systematic-research",
        filename="blocked.pdf",
        media_type="application/pdf",
        content_digest="a" * 64,
        source={"title": "Blocked paper", "origin": "founder-inbox://blocked.pdf"},
        status=status,
        created_at=now,
        updated_at=now,
    )


def test_register_exposes_terminal_action_and_attempt_ledger() -> None:
    now = datetime.now(timezone.utc)
    recovery = SimpleNamespace(
        id=UUID("20000000-0000-4000-8000-000000000001"),
        status="rejected",
        receipt={
            "terminal_classification": "security_blocked",
            "founder_action": "Review the redacted edition proposal.",
            "attempts": [
                {
                    "number": 1,
                    "method": "structural_repair",
                    "pipeline_status": "rejected",
                }
            ],
            "redacted_edition_proposal": {
                "publication_authorized": False,
                "founder_approval_required": True,
            },
        },
        updated_at=now,
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = [(_job(), recovery)]

    result = blocked_artifact_register(db)

    assert result.total == 1
    assert result.counts_by_classification == {"security_blocked": 1}
    item = result.items[0]
    assert item.retry_eligible is False
    assert item.attempted_methods == ["structural_repair"]
    assert item.redacted_edition_proposal["publication_authorized"] is False


def test_register_marks_unprocessed_quarantine_recovery_eligible() -> None:
    db = MagicMock()
    db.execute.return_value.all.return_value = [(_job(status="quarantined"), None)]

    item = blocked_artifact_register(db).items[0]

    assert item.classification == "awaiting_recovery"
    assert item.retry_eligible is True
    assert "bounded recovery steward" in item.action_required


def test_register_excludes_recovered_originals() -> None:
    recovery = SimpleNamespace(status="recovered")
    db = MagicMock()
    db.execute.return_value.all.return_value = [(_job(), recovery)]

    assert blocked_artifact_register(db).total == 0
