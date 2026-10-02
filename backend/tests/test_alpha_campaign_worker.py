from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

from app.workers import alpha_campaign as worker


class FakeSession:
    def __init__(self, campaigns):
        self.campaigns = campaigns
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def scalars(self, _query):
        return SimpleNamespace(all=lambda: self.campaigns)

    def begin_nested(self):
        return nullcontext()

    def commit(self):
        self.committed = True


def test_campaign_failure_does_not_block_other_reconciliation(monkeypatch):
    blocked = SimpleNamespace(
        id=uuid4(),
        status="running",
        phase="strategy_engineering",
        next_action="await_bounded_strategy_engineering",
        hypothesis_count=1,
        trial_count=0,
        created_at=None,
    )
    healthy = SimpleNamespace(
        id=uuid4(),
        status="running",
        phase="strategy_engineering",
        next_action="await_bounded_strategy_engineering",
        hypothesis_count=1,
        trial_count=0,
        created_at=None,
    )
    session = FakeSession([blocked, healthy])

    def reconcile(_db, campaign):
        if campaign is blocked:
            raise ValueError("retained malformed campaign")
        campaign.phase = "strategy_qualification"
        campaign.next_action = "await_independent_review"

    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker, "reconcile_campaign", reconcile)

    result = worker.run_once()

    assert session.committed
    assert result["failed_campaigns"] == [
        {
            "campaign_id": str(blocked.id),
            "error": "ValueError",
            "detail": "retained malformed campaign",
        }
    ]
    assert healthy.phase == "strategy_qualification"
    assert healthy.next_action == "await_independent_review"
