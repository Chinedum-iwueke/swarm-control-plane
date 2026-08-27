from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.autonomous_research import router
from app.schemas.autonomous_research import (
    AutonomousResearchSessionCreate,
    AutonomousSessionCheckpoint,
    AutonomousSessionCloseout,
)
from app.services import autonomous_research as service
from fastapi import HTTPException
from pydantic import ValidationError

DIGEST = "a" * 64


def node(key="spec", *, risk=0):
    return SimpleNamespace(
        node_key=key,
        role="research-specialist",
        output_type="research.result.v1",
        task_spec={"risk_level": risk},
        task_id=None,
        status="blocked",
        ordinal=0,
    )


def graph(**updates):
    value = {
        "id": uuid4(),
        "status": "draft",
        "project": "bulletproof-bt",
        "manifest_digest": DIGEST,
        "max_total_attempts": 4,
        "max_duration_seconds": 600,
    }
    value.update(updates)
    return SimpleNamespace(**value)


def request(**updates):
    value = {
        "session_key": "DISC008-SESSION-1",
        "project": "bulletproof-bt",
        "objective": "Run one bounded no-capital research session.",
        "task_graph_id": uuid4(),
        "agenda": [{
            "node_key": "spec",
            "role": "research-specialist",
            "expected_output_type": "research.result.v1",
        }],
        "budget": {
            "max_tasks": 1,
            "max_total_attempts": 2,
            "max_duration_seconds": 300,
            "max_reconciliations": 5,
            "max_no_progress_reconciliations": 2,
            "max_worker_losses": 1,
        },
        "stop_conditions": ["Budget exhausted."],
        "escalation_conditions": ["Research conflict detected."],
        "allowed_scope": ["registered synthetic experiment"],
        "created_by": "founder-operator",
    }
    value.update(updates)
    return AutonomousResearchSessionCreate.model_validate(value)


def session(**updates):
    value = {
        "id": uuid4(),
        "status": "active",
        "task_graph_id": uuid4(),
        "task_graph_digest": DIGEST,
        "agenda_digest": "e" * 64,
        "budget_digest": "f" * 64,
        "agenda": {"items": [{"node_key": "spec"}]},
        "budget": {
            "max_reconciliations": 5,
            "max_no_progress_reconciliations": 2,
            "max_worker_losses": 1,
        },
        "reconcile_count": 0,
        "no_progress_count": 0,
        "worker_loss_count": 0,
        "last_progress_digest": "b" * 64,
        "terminal_reason": {},
        "closeout": {},
        "completed_at": None,
    }
    value.update(updates)
    return SimpleNamespace(**value)


def test_contract_is_explicitly_no_capital_and_no_self_approval():
    payload = request()
    assert payload.authority == "no_capital"
    assert payload.may_approve is payload.may_expand_scope is payload.may_promote is False


def test_agenda_size_must_equal_task_budget():
    with pytest.raises(ValidationError, match="max_tasks"):
        request(budget={
            "max_tasks": 2, "max_total_attempts": 2, "max_duration_seconds": 300,
            "max_reconciliations": 5, "max_no_progress_reconciliations": 2,
        })


@pytest.mark.parametrize("change, message", [
    ({"status": "active"}, "unactivated"),
    ({"project": "other"}, "project"),
])
def test_registration_requires_matching_draft_graph(monkeypatch, change, message):
    db = MagicMock()
    db.get.return_value = graph(**change)
    monkeypatch.setattr(service, "_nodes", lambda *_: [node()])
    with pytest.raises(HTTPException, match=message):
        service.register_session(db, request())


def test_registration_rejects_scope_or_risk_drift(monkeypatch):
    db = MagicMock()
    db.get.return_value = graph()
    monkeypatch.setattr(service, "_nodes", lambda *_: [node(risk=1)])
    with pytest.raises(HTTPException, match="risk level zero"):
        service.register_session(db, request())


def test_registration_freezes_graph_agenda_and_budgets(monkeypatch):
    db = MagicMock()
    db.get.return_value = graph()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_nodes", lambda *_: [node()])
    record = service.register_session(db, request())
    assert record.task_graph_digest == DIGEST
    assert record.agenda["authority"] == "no_capital"
    assert record.agenda_digest != record.budget_digest


def test_checkpoint_outside_frozen_agenda_fails_closed():
    payload = AutonomousSessionCheckpoint(
        kind="progress", actor="supervisor", node_key="invented",
        detail="scope drift", evidence_digest=DIGEST,
    )
    with pytest.raises(HTTPException, match="outside"):
        service.record_checkpoint(MagicMock(), session(), payload)


def test_conflict_checkpoint_escalates_and_retains_evidence(monkeypatch):
    record = session()
    monkeypatch.setattr(service, "append_event", MagicMock())
    failed = MagicMock()
    monkeypatch.setattr(service, "_fail_closed", failed)
    service.record_checkpoint(MagicMock(), record, AutonomousSessionCheckpoint(
        kind="conflict", actor="adversarial-reviewer", node_key="spec",
        detail="evidence conflict", evidence_digest=DIGEST,
    ))
    failed.assert_called_once()
    assert failed.call_args.args[2] == "research_conflict"


def test_worker_loss_budget_is_bounded(monkeypatch):
    record = session(worker_loss_count=1)
    monkeypatch.setattr(service, "append_event", MagicMock())
    failed = MagicMock()
    monkeypatch.setattr(service, "_fail_closed", failed)
    service.record_checkpoint(MagicMock(), record, AutonomousSessionCheckpoint(
        kind="worker_loss", actor="supervisor", node_key="spec",
        detail="lease lost", evidence_digest=DIGEST,
    ))
    assert record.worker_loss_count == 2
    assert failed.call_args.args[2] == "worker_loss_budget_exceeded"


def test_repeated_no_progress_escalates(monkeypatch):
    record = session(no_progress_count=2)
    bound_graph = graph(status="active", id=record.task_graph_id)
    db = MagicMock()
    db.get.return_value = bound_graph
    monkeypatch.setattr(service, "reconcile_graph", MagicMock())
    monkeypatch.setattr(service, "_progress_digest", lambda *_: "b" * 64)
    failed = MagicMock()
    monkeypatch.setattr(service, "_fail_closed", failed)
    service.reconcile_session(db, record)
    assert failed.call_args.args[2] == "no_progress_budget_exceeded"


def test_closeout_requires_independence_and_selection_audit():
    db = MagicMock()
    db.get.return_value = None
    db.scalar.return_value = None
    with pytest.raises(HTTPException, match="independent"):
        service.close_session(db, session(status="awaiting_closeout"), AutonomousSessionCloseout(
            actor="supervisor", evaluation_route_id=uuid4(), selection_audit_id=uuid4(),
            dossier={}, dossier_digest=DIGEST, retained_outcomes=["negative", "failed"],
        ))


def test_successful_closeout_binds_independence_audit_and_all_outcomes(monkeypatch):
    record = session(status="awaiting_closeout")
    route_id = uuid4()
    audit_id = uuid4()
    route = SimpleNamespace(
        id=route_id, status="completed", subject_type="autonomous_research_session",
        subject_id=str(record.id), subject_digest=DIGEST,
    )
    audit = SimpleNamespace(id=audit_id, status="active", audit_digest="c" * 64)
    receipt = SimpleNamespace(subject_digest=DIGEST, receipt_digest="d" * 64)
    db = MagicMock()
    db.get.side_effect = lambda _model, identifier: route if identifier == route_id else audit
    db.scalar.return_value = receipt
    monkeypatch.setattr(service, "append_event", MagicMock())
    monkeypatch.setattr(service, "_nodes", lambda *_: [])
    retained = ["positive", "negative", "invalid", "failed", "cancelled"]
    dossier = {
        "session_id": str(record.id),
        "task_graph_digest": record.task_graph_digest,
        "agenda_digest": record.agenda_digest,
        "budget_digest": record.budget_digest,
        "selection_audit_digest": audit.audit_digest,
        "retained_outcomes": retained,
    }
    route.subject_digest = service.digest(dossier)
    receipt.subject_digest = route.subject_digest
    service.close_session(db, record, AutonomousSessionCloseout(
        actor="supervisor", evaluation_route_id=route_id, selection_audit_id=audit_id,
        dossier=dossier, dossier_digest=service.digest(dossier), retained_outcomes=retained,
    ))
    assert record.status == "completed"
    assert record.closeout["independence_receipt_digest"] == "d" * 64
    assert record.closeout["selection_audit_digest"] == "c" * 64
    assert record.closeout["closeout_digest"]


def test_graph_success_waits_for_independent_closeout(monkeypatch):
    record = session()
    bound_graph = graph(status="succeeded", id=record.task_graph_id)
    db = MagicMock()
    db.get.return_value = bound_graph
    monkeypatch.setattr(service, "reconcile_graph", MagicMock())
    monkeypatch.setattr(service, "_progress_digest", lambda *_: "c" * 64)
    monkeypatch.setattr(service, "append_event", MagicMock())
    service.reconcile_session(db, record)
    assert record.status == "awaiting_closeout"
    assert record.completed_at is None


def test_routes_expose_full_bounded_lifecycle():
    paths = {route.path for route in router.routes}
    assert {
        "/v1/research/autonomous-sessions",
        "/v1/research/autonomous-sessions/{session_id}/activate",
        "/v1/research/autonomous-sessions/{session_id}/checkpoints",
        "/v1/research/autonomous-sessions/{session_id}/reconcile",
        "/v1/research/autonomous-sessions/{session_id}/closeout",
        "/v1/research/autonomous-sessions/{session_id}/cancel",
    }.issubset(paths)
