from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services import alpha_discovery as discovery
from app.services import alpha_requirements_correction as correction


def test_lineage_counts_corrections_and_rejects_cycles():
    parent = NS(id=uuid4(), cycle_id=uuid4(), candidate_digest="parent")
    child = NS(id=uuid4(), cycle_id=uuid4(), candidate_digest="child")
    scope = {"schema_version": 3, "candidate_id": str(parent.id), "candidate_digest": "parent"}
    root_cycle = NS(context={})
    child_cycle = NS(context={"founder_research_idea": {"constraints": {"retained_candidate_recovery": scope}}})
    objects = {parent.id: parent, child.id: child, parent.cycle_id: root_cycle, child.cycle_id: child_cycle}
    db = MagicMock()
    db.get.side_effect = lambda model, key: objects.get(key)
    assert correction.correction_depth(db, child) == 1
    root_cycle.context = {"founder_research_idea": {"constraints": {"retained_candidate_recovery": {
        "schema_version": 3, "candidate_id": str(child.id), "candidate_digest": "child"}}}}
    with pytest.raises(ValueError, match="cyclic"):
        correction.correction_depth(db, child)


@pytest.mark.parametrize("blocked", ["paused", "budget", "expired", "inactive"])
def test_no_work_outside_authority(monkeypatch, blocked):
    now = datetime.now(UTC)
    mandate = NS(id=uuid4(), status="completed" if blocked == "inactive" else "active",
        valid_from=now-timedelta(days=1),
        valid_until=now-timedelta(seconds=1) if blocked == "expired" else now+timedelta(days=1))
    monkeypatch.setattr(discovery, "_mandate_budget_exhausted", lambda _: blocked == "budget")
    monkeypatch.setattr(discovery, "_discovery_creation_paused", lambda _: blocked == "paused")
    db = MagicMock()
    monkeypatch.setattr(correction, "retain_disposition", MagicMock())
    assert correction.queue_requirements_correction(db, mandate) is None
    db.add.assert_not_called()
    db.scalars.assert_not_called()


def test_verified_rejection_queues_once_with_controller_identity(monkeypatch):
    monkeypatch.setattr(correction, "retain_disposition", MagicMock(return_value={"disposition": "repair"}))
    now = datetime.now(UTC)
    mandate = NS(id=uuid4(), mandate_digest="mandate", status="active",
        valid_from=now-timedelta(days=1), valid_until=now+timedelta(days=1))
    candidate = NS(id=uuid4(), candidate_digest="candidate", question="A predictive question?",
        document={"parameter_budget": {"maximum_variants": 1}})
    publication = NS(id=3, payload={"subject": {"candidate_id": str(candidate.id)}})
    scope = {"scientific_identity": {"data": {"instruments": ["BTCUSDT"]}},
        "rejection_subject_digest": "rejection", "review_blockers": ["Fix estimator"]}
    monkeypatch.setattr(discovery, "_mandate_budget_exhausted", lambda _: False)
    monkeypatch.setattr(discovery, "_discovery_creation_paused", lambda _: False)
    event = MagicMock()
    monkeypatch.setattr(discovery, "_event", event)
    monkeypatch.setattr(correction, "correction_depth", lambda *a: 0)
    verifier = MagicMock(return_value=scope)
    monkeypatch.setattr(correction, "recovery_scope", verifier)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [publication]
    db.get.return_value = candidate
    db.scalar.return_value = None
    idea = correction.queue_requirements_correction(db, mandate)
    assert idea.submitted_by == "requirements-correction-controller"
    assert idea.constraints["retained_candidate_recovery"] == scope
    assert event.call_args.args[2] == "requirements_correction_queued"
    assert verifier.call_args.kwargs["schema_version"] == 3
    db.scalar.return_value = uuid4()
    assert correction.queue_requirements_correction(db, mandate) is None
    assert db.add.call_count == 1
    monkeypatch.setattr(correction, "correction_depth", lambda *a: 0)
    verifier.side_effect = ValueError("no validated independent rejection")
    assert correction.queue_requirements_correction(db, mandate) is None
    assert db.add.call_count == 1
    db.scalar.return_value = None
    monkeypatch.setattr(correction, "correction_depth", lambda *a: 2)
    assert correction.queue_requirements_correction(db, mandate) is None
    assert db.add.call_count == 1
