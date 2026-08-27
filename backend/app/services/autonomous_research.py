from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.models.autonomous_research import (
    AutonomousResearchSession,
    AutonomousResearchSessionEvent,
)
from app.models.evaluator_routing import EvaluationIndependenceReceipt, EvaluationRoute
from app.models.selection_audit import SelectionBiasAudit
from app.models.task_graph import TaskGraph, TaskGraphNode
from app.schemas.autonomous_research import (
    AutonomousResearchSessionCreate,
    AutonomousSessionCheckpoint,
    AutonomousSessionCloseout,
)
from app.services.task_graphs import (
    activate_graph,
    cancel_graph,
    digest,
    reconcile_graph,
)

ACTIVE = {"active", "awaiting_closeout"}
TERMINAL_GRAPH = {"succeeded", "failed", "cancelled", "compensated", "compensation_failed"}


def now() -> datetime:
    return datetime.now(UTC)


def append_event(db: Session, session: AutonomousResearchSession, event_type: str, actor: str, payload: dict):
    prior = db.scalar(
        select(AutonomousResearchSessionEvent)
        .where(AutonomousResearchSessionEvent.session_id == session.id)
        .order_by(AutonomousResearchSessionEvent.sequence.desc())
        .limit(1)
    )
    sequence = (prior.sequence if prior else 0) + 1
    previous_digest = prior.event_digest if prior else None
    event_digest = digest({
        "session_id": str(session.id), "sequence": sequence, "event_type": event_type,
        "actor": actor, "payload": payload, "previous_digest": previous_digest,
    })
    event = AutonomousResearchSessionEvent(
        session_id=session.id, sequence=sequence, event_type=event_type, actor=actor,
        payload=payload, previous_digest=previous_digest, event_digest=event_digest,
    )
    db.add(event)
    db.flush()
    return event


def _nodes(db: Session, graph_id):
    return db.scalars(
        select(TaskGraphNode).where(TaskGraphNode.graph_id == graph_id).order_by(TaskGraphNode.ordinal)
    ).all()


def register_session(db: Session, payload: AutonomousResearchSessionCreate) -> AutonomousResearchSession:
    graph = db.get(TaskGraph, payload.task_graph_id)
    if graph is None:
        raise HTTPException(404, "Task graph not found.")
    if graph.status != "draft":
        raise HTTPException(409, "Autonomous sessions require an unactivated task graph.")
    if graph.project != payload.project:
        raise HTTPException(422, "Session project does not match its task graph.")
    nodes = _nodes(db, graph.id)
    expected = [(node.node_key, node.role, node.output_type) for node in nodes]
    observed = [(item.node_key, item.role, item.expected_output_type) for item in payload.agenda]
    if observed != expected:
        raise HTTPException(422, "Frozen agenda must exactly match the ordered task graph.")
    if any(int(node.task_spec.get("risk_level", -1)) != 0 for node in nodes):
        raise HTTPException(422, "Autonomous research session tasks must all be risk level zero.")
    if payload.budget.max_total_attempts > graph.max_total_attempts:
        raise HTTPException(422, "Session attempt budget cannot exceed the task graph budget.")
    if payload.budget.max_duration_seconds > graph.max_duration_seconds:
        raise HTTPException(422, "Session duration cannot exceed the task graph duration.")
    agenda = {
        "items": [item.model_dump(mode="json") for item in payload.agenda],
        "stop_conditions": payload.stop_conditions,
        "escalation_conditions": payload.escalation_conditions,
        "allowed_scope": payload.allowed_scope,
        "authority": payload.authority,
        "may_approve": payload.may_approve,
        "may_expand_scope": payload.may_expand_scope,
        "may_promote": payload.may_promote,
    }
    budget = payload.budget.model_dump(mode="json")
    session = AutonomousResearchSession(
        session_key=payload.session_key, project=payload.project, objective=payload.objective,
        task_graph_id=graph.id, task_graph_digest=graph.manifest_digest, agenda=agenda,
        agenda_digest=digest(agenda), budget=budget, budget_digest=digest(budget),
        status="draft", created_by=payload.created_by, terminal_reason={}, closeout={},
    )
    db.add(session)
    db.flush()
    append_event(db, session, "session_registered", payload.created_by, {
        "task_graph_digest": graph.manifest_digest,
        "agenda_digest": session.agenda_digest,
        "budget_digest": session.budget_digest,
    })
    return session


def _progress_digest(db: Session, session: AutonomousResearchSession, graph: TaskGraph) -> str:
    nodes = _nodes(db, graph.id)
    state = []
    for node in nodes:
        task = db.get(Task, node.task_id) if node.task_id else None
        state.append({
            "node": node.node_key,
            "node_status": node.status,
            "task_status": task.status if task else None,
            "attempts": task.attempt_count if task else 0,
        })
    return digest({"graph_status": graph.status, "nodes": state})


def activate_session(db: Session, session: AutonomousResearchSession, actor: str) -> None:
    if session.status != "draft":
        raise HTTPException(409, "Only a draft autonomous session can be activated.")
    graph = db.get(TaskGraph, session.task_graph_id)
    if graph is None or graph.manifest_digest != session.task_graph_digest:
        raise HTTPException(409, "Bound task graph is missing or has drifted.")
    activate_graph(db, graph, actor)
    session.status = "active"
    session.activated_at = now()
    session.last_progress_digest = _progress_digest(db, session, graph)
    append_event(db, session, "session_activated", actor, {"task_graph_id": str(graph.id)})


def _fail_closed(db: Session, session: AutonomousResearchSession, category: str, detail: dict) -> None:
    graph = db.get(TaskGraph, session.task_graph_id)
    affected = 0
    if graph and graph.status in {"active", "cancelling", "compensating"}:
        if graph.status == "active":
            affected = cancel_graph(db, graph, "autonomous-research-supervisor", category)
        reconcile_graph(db, graph)
    session.status = "escalated"
    session.terminal_reason = {"category": category, **detail, "tasks_affected": affected}
    session.completed_at = now()
    append_event(db, session, "session_escalated", "autonomous-research-supervisor", session.terminal_reason)


def record_checkpoint(db: Session, session: AutonomousResearchSession, payload: AutonomousSessionCheckpoint) -> None:
    if session.status != "active":
        raise HTTPException(409, "Checkpoints are accepted only for active sessions.")
    node_keys = {item["node_key"] for item in session.agenda["items"]}
    if payload.node_key and payload.node_key not in node_keys:
        raise HTTPException(422, "Checkpoint node is outside the frozen agenda.")
    append_event(db, session, f"checkpoint_{payload.kind}", payload.actor, payload.model_dump(mode="json"))
    if payload.kind == "progress":
        session.no_progress_count = 0
    elif payload.kind == "no_progress":
        session.no_progress_count += 1
        if session.no_progress_count > session.budget["max_no_progress_reconciliations"]:
            _fail_closed(db, session, "no_progress_budget_exceeded", {"evidence_digest": payload.evidence_digest})
    elif payload.kind == "worker_loss":
        session.worker_loss_count += 1
        if session.worker_loss_count > session.budget["max_worker_losses"]:
            _fail_closed(db, session, "worker_loss_budget_exceeded", {"evidence_digest": payload.evidence_digest})
    elif payload.kind == "conflict":
        _fail_closed(db, session, "research_conflict", {"evidence_digest": payload.evidence_digest, "detail": payload.detail})


def reconcile_session(db: Session, session: AutonomousResearchSession) -> None:
    if session.status != "active":
        return
    graph = db.get(TaskGraph, session.task_graph_id)
    if graph is None or graph.manifest_digest != session.task_graph_digest:
        _fail_closed(db, session, "task_graph_drift", {})
        return
    session.reconcile_count += 1
    reconcile_graph(db, graph)
    current = _progress_digest(db, session, graph)
    if current == session.last_progress_digest:
        session.no_progress_count += 1
    else:
        session.no_progress_count = 0
        session.last_progress_digest = current
        append_event(db, session, "session_progressed", "autonomous-research-supervisor", {"progress_digest": current})
    if session.reconcile_count > session.budget["max_reconciliations"]:
        _fail_closed(db, session, "reconciliation_budget_exceeded", {})
    elif session.no_progress_count > session.budget["max_no_progress_reconciliations"]:
        _fail_closed(db, session, "no_progress_budget_exceeded", {})
    elif graph.status == "succeeded":
        session.status = "awaiting_closeout"
        append_event(db, session, "research_work_completed", "autonomous-research-supervisor", {"task_graph_status": graph.status})
    elif graph.status in TERMINAL_GRAPH:
        session.status = "failed"
        session.terminal_reason = {"category": "task_graph_terminal", "task_graph_status": graph.status}
        session.completed_at = now()
        append_event(db, session, "session_failed", "autonomous-research-supervisor", session.terminal_reason)


def close_session(db: Session, session: AutonomousResearchSession, payload: AutonomousSessionCloseout) -> None:
    if session.status != "awaiting_closeout":
        raise HTTPException(409, "Session research work is not ready for independent closeout.")
    route = db.get(EvaluationRoute, payload.evaluation_route_id)
    receipt = db.scalar(select(EvaluationIndependenceReceipt).where(EvaluationIndependenceReceipt.route_id == payload.evaluation_route_id))
    if route is None or route.status != "completed" or receipt is None:
        raise HTTPException(422, "A completed independent evaluation route and receipt are required.")
    if route.subject_type != "autonomous_research_session" or route.subject_id != str(session.id):
        raise HTTPException(422, "Independent evaluation route does not identify this session.")
    if route.subject_digest != payload.dossier_digest or receipt.subject_digest != payload.dossier_digest:
        raise HTTPException(422, "Independent evaluation is not bound to the closeout dossier.")
    audit = db.get(SelectionBiasAudit, payload.selection_audit_id)
    if audit is None or audit.status != "active":
        raise HTTPException(422, "An active selection-bias audit is required.")
    if digest(payload.dossier) != payload.dossier_digest:
        raise HTTPException(422, "Closeout dossier digest does not match its canonical content.")
    required_dossier = {
        "session_id": str(session.id),
        "task_graph_digest": session.task_graph_digest,
        "agenda_digest": session.agenda_digest,
        "budget_digest": session.budget_digest,
        "selection_audit_digest": audit.audit_digest,
        "retained_outcomes": payload.retained_outcomes,
    }
    if any(payload.dossier.get(key) != value for key, value in required_dossier.items()):
        raise HTTPException(422, "Closeout dossier is not bound to the session, audit and outcomes.")
    graph = db.get(TaskGraph, session.task_graph_id)
    observed_outcomes = set()
    for node in _nodes(db, graph.id):
        task = db.get(Task, node.task_id) if node.task_id else None
        outcome = (task.result or {}).get("scientific_outcome") if task else None
        if outcome in {"positive", "negative", "invalid", "failed", "cancelled"}:
            observed_outcomes.add(outcome)
    if not observed_outcomes.issubset(set(payload.retained_outcomes)):
        raise HTTPException(422, "Closeout omits observed scientific outcomes.")
    closeout = payload.model_dump(mode="json")
    closeout["independence_receipt_digest"] = receipt.receipt_digest
    closeout["selection_audit_digest"] = audit.audit_digest
    closeout["closeout_digest"] = digest(closeout)
    session.closeout = closeout
    session.status = "completed"
    session.completed_at = now()
    append_event(db, session, "session_completed", payload.actor, closeout)


def cancel_session(db: Session, session: AutonomousResearchSession, actor: str, reason: str) -> None:
    if session.status not in {"draft", "active", "awaiting_closeout"}:
        raise HTTPException(409, "Only a non-terminal session can be cancelled.")
    graph = db.get(TaskGraph, session.task_graph_id)
    affected = 0
    if graph and graph.status == "active":
        affected = cancel_graph(db, graph, actor, reason)
        reconcile_graph(db, graph)
    session.status = "cancelled"
    session.terminal_reason = {"category": "operator_cancelled", "reason": reason, "tasks_affected": affected}
    session.completed_at = now()
    append_event(db, session, "session_cancelled", actor, session.terminal_reason)


def serialize_session(db: Session, session: AutonomousResearchSession) -> dict:
    events = db.scalars(
        select(AutonomousResearchSessionEvent)
        .where(AutonomousResearchSessionEvent.session_id == session.id)
        .order_by(AutonomousResearchSessionEvent.sequence)
    ).all()
    return {
        "id": session.id, "session_key": session.session_key, "project": session.project,
        "objective": session.objective, "task_graph_id": session.task_graph_id,
        "task_graph_digest": session.task_graph_digest, "agenda": session.agenda,
        "agenda_digest": session.agenda_digest, "budget": session.budget,
        "budget_digest": session.budget_digest, "status": session.status,
        "reconcile_count": session.reconcile_count, "no_progress_count": session.no_progress_count,
        "worker_loss_count": session.worker_loss_count, "terminal_reason": session.terminal_reason,
        "closeout": session.closeout, "created_by": session.created_by, "created_at": session.created_at,
        "activated_at": session.activated_at, "completed_at": session.completed_at,
        "events": [{
            "sequence": event.sequence, "event_type": event.event_type, "actor": event.actor,
            "payload": event.payload, "previous_digest": event.previous_digest,
            "event_digest": event.event_digest, "created_at": event.created_at,
        } for event in events],
    }
