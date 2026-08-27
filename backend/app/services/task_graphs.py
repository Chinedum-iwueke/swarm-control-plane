from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskDependency
from app.models.task_graph import (
    TaskGraph,
    TaskGraphEvent,
    TaskGraphMessage,
    TaskGraphNode,
)
from app.schemas.task import TaskCreate
from app.schemas.task_graph import (
    GraphTaskSpec,
    TaskGraphCreate,
    TaskGraphMessageCreate,
)
from app.services.agent_context import discard_working_memory
from app.services.tasks import (
    append_task_event,
    build_task,
    clear_lease,
    persist_new_task,
)

TERMINAL_TASK = {"succeeded", "failed", "cancelled"}
ACTIVE_GRAPH = {"active", "cancelling", "compensating"}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def now() -> datetime:
    return datetime.now(UTC)


def append_event(db: Session, graph: TaskGraph, event_type: str, actor: str, payload: dict) -> TaskGraphEvent:
    previous = db.scalar(select(TaskGraphEvent).where(TaskGraphEvent.graph_id == graph.id).order_by(TaskGraphEvent.sequence.desc()).limit(1))
    sequence = (previous.sequence if previous else 0) + 1
    previous_digest = previous.event_digest if previous else None
    event_digest = digest({"graph_id": str(graph.id), "sequence": sequence, "event_type": event_type, "actor": actor, "payload": payload, "previous_digest": previous_digest})
    event = TaskGraphEvent(graph_id=graph.id, sequence=sequence, event_type=event_type, actor=actor, payload=payload, previous_digest=previous_digest, event_digest=event_digest)
    db.add(event)
    db.flush()
    return event


def create_graph(db: Session, payload: TaskGraphCreate) -> TaskGraph:
    document = payload.model_dump(mode="json")
    graph = TaskGraph(
        graph_key=payload.graph_key, project=payload.project, objective=payload.objective,
        status="draft", schema_version="typed-task-graph-v1.0.0", manifest=document,
        manifest_digest=digest(document), max_nodes=payload.max_nodes,
        max_total_attempts=payload.max_total_attempts, max_duration_seconds=payload.max_duration_seconds,
        max_parallelism=payload.max_parallelism, created_by=payload.created_by, terminal_reason={},
    )
    db.add(graph)
    db.flush()
    for ordinal, item in enumerate(payload.nodes):
        db.add(TaskGraphNode(
            graph_id=graph.id, node_key=item.key, role=item.role, node_type=item.node_type,
            status="blocked", depends_on=item.depends_on, input_type=item.input_type,
            output_type=item.output_type, task_spec=item.task.model_dump(mode="json"),
            stop_conditions=item.stop_conditions,
            compensation=item.compensation.model_dump(mode="json") if item.compensation else {},
            ordinal=ordinal,
        ))
    append_event(db, graph, "graph_created", payload.created_by, {"manifest_digest": graph.manifest_digest, "node_count": len(payload.nodes)})
    return graph


def _task_payload(graph: TaskGraph, node: TaskGraphNode, spec: GraphTaskSpec, suffix: str = "") -> TaskCreate:
    return TaskCreate(
        task_number=f"{graph.graph_key}-{node.node_key}{suffix}", project=graph.project,
        task_type=spec.task_type, title=spec.title, objective=spec.objective,
        created_by=graph.created_by, input_contract={**spec.input_contract, "task_graph": {"graph_id": str(graph.id), "node_key": node.node_key, "manifest_digest": graph.manifest_digest}},
        expected_outputs=spec.expected_outputs, acceptance_criteria=spec.acceptance_criteria,
        required_capabilities=spec.required_capabilities, allowed_machines=spec.allowed_machines,
        max_attempts=spec.max_attempts, risk_level=spec.risk_level,
    )


def activate_graph(db: Session, graph: TaskGraph, actor: str) -> None:
    if graph.status != "draft":
        raise HTTPException(409, "Only a draft task graph can be activated.")
    nodes = db.scalars(select(TaskGraphNode).where(TaskGraphNode.graph_id == graph.id).order_by(TaskGraphNode.ordinal)).all()
    tasks: dict[str, Task] = {}
    for node in nodes:
        task = build_task(_task_payload(graph, node, GraphTaskSpec.model_validate(node.task_spec)))
        task.task_graph_node_id = node.id
        persist_new_task(db, task)
        node.task_id = task.id
        node.status = task.status
        tasks[node.node_key] = task
    for node in nodes:
        for dependency in node.depends_on:
            db.add(TaskDependency(task_id=tasks[node.node_key].id, depends_on_task_id=tasks[dependency].id))
    stamp = now()
    graph.status = "active"
    graph.activated_at = stamp
    graph.deadline_at = stamp + timedelta(seconds=graph.max_duration_seconds)
    append_event(db, graph, "graph_activated", actor, {"deadline_at": graph.deadline_at.isoformat(), "task_ids": {key: str(task.id) for key, task in tasks.items()}})


def append_message(db: Session, graph: TaskGraph, payload: TaskGraphMessageCreate) -> TaskGraphMessage:
    if graph.status not in ACTIVE_GRAPH:
        raise HTTPException(409, "Messages are accepted only while a graph is active.")
    node = None
    if payload.node_key:
        node = db.scalar(select(TaskGraphNode).where(TaskGraphNode.graph_id == graph.id, TaskGraphNode.node_key == payload.node_key))
        if node is None:
            raise HTTPException(404, "Task graph node not found.")
        if payload.message_type not in {node.input_type, node.output_type, "control.cancel", "evidence.receipt", "failure.report"}:
            raise HTTPException(422, "Message type is not declared by the target node.")
    sequence = (db.scalar(select(func.max(TaskGraphMessage.sequence)).where(TaskGraphMessage.graph_id == graph.id)) or 0) + 1
    message = TaskGraphMessage(graph_id=graph.id, node_id=node.id if node else None, sequence=sequence, message_type=payload.message_type, sender=payload.sender, recipient=payload.recipient, payload=payload.payload, payload_digest=digest(payload.payload))
    db.add(message)
    append_event(db, graph, "typed_message_recorded", payload.sender, {"sequence": sequence, "message_type": payload.message_type, "payload_digest": message.payload_digest})
    return message


def _cancel_task(db: Session, task: Task, reason: str) -> bool:
    if task.status in TERMINAL_TASK:
        return False
    stamp = now()
    if task.status in {"leased", "running"}:
        task.cancel_requested_at = stamp
        task.cancel_reason = reason
        append_task_event(db, task, "task_cancellation_requested", reason, payload={"cooperative": True})
    else:
        task.status = "cancelled"
        task.cancel_requested_at = stamp
        task.cancel_reason = reason
        task.completed_at = stamp
        clear_lease(task)
        discard_working_memory(db, task.id)
        append_task_event(db, task, "task_cancelled", reason, payload={"cooperative": False})
    return True


def cancel_graph(db: Session, graph: TaskGraph, actor: str, reason: str) -> int:
    if graph.status not in ACTIVE_GRAPH:
        raise HTTPException(409, "Only an active task graph can be cancelled.")
    graph.status = "cancelling"
    changed = 0
    for node in db.scalars(select(TaskGraphNode).where(TaskGraphNode.graph_id == graph.id)).all():
        task = db.get(Task, node.task_id) if node.task_id else None
        if task and _cancel_task(db, task, reason):
            changed += 1
    graph.terminal_reason = {"category": "operator_cancelled", "reason": reason}
    append_event(db, graph, "graph_cancellation_requested", actor, {"reason": reason, "tasks_affected": changed})
    return changed


def _create_compensations(db: Session, graph: TaskGraph, nodes: list[TaskGraphNode]) -> int:
    created = 0
    for node in sorted(nodes, key=lambda item: item.ordinal, reverse=True):
        original = db.get(Task, node.task_id) if node.task_id else None
        if not original or original.status != "succeeded" or not node.compensation:
            continue
        existing = db.scalar(select(Task).where(Task.task_number == f"{graph.graph_key}-{node.node_key}-compensate"))
        if existing:
            continue
        spec = GraphTaskSpec.model_validate(node.compensation)
        task = build_task(_task_payload(graph, node, spec, "-compensate"))
        task.parent_task_id = original.id
        persist_new_task(db, task)
        created += 1
        append_event(db, graph, "compensation_materialized", "task-graph-controller", {"node_key": node.node_key, "task_id": str(task.id), "original_task_id": str(original.id)})
    return created


def reconcile_graph(db: Session, graph: TaskGraph) -> tuple[int, int]:
    if graph.status not in ACTIVE_GRAPH:
        return 0, 0
    nodes = db.scalars(select(TaskGraphNode).where(TaskGraphNode.graph_id == graph.id).order_by(TaskGraphNode.ordinal)).all()
    transitioned = 0
    attempts = 0
    tasks: list[Task] = []
    for node in nodes:
        task = db.get(Task, node.task_id) if node.task_id else None
        if task:
            tasks.append(task)
            attempts += task.attempt_count
            if node.status != task.status:
                node.status = task.status
                transitioned += 1
    if graph.status == "compensating":
        compensations = db.scalars(
            select(Task).where(Task.task_number.like(f"{graph.graph_key}-%-compensate"))
        ).all()
        if compensations and all(task.status in TERMINAL_TASK for task in compensations):
            graph.status = "compensated" if all(task.status == "succeeded" for task in compensations) else "compensation_failed"
            graph.completed_at = now()
            append_event(
                db, graph, "graph_compensation_completed", "task-graph-controller",
                {"status": graph.status, "task_ids": [str(task.id) for task in compensations]},
            )
        return transitioned, 0
    stamp = now()
    budget_reason = None
    if graph.deadline_at and stamp >= graph.deadline_at:
        budget_reason = "graph_deadline_exceeded"
    elif attempts > graph.max_total_attempts:
        budget_reason = "graph_attempt_budget_exceeded"
    failed = [task for task in tasks if task.status == "failed"]
    if budget_reason or failed:
        reason = budget_reason or "dependency_failed"
        for task in tasks:
            _cancel_task(db, task, reason)
        graph.status = "compensating"
        graph.terminal_reason = {"category": reason, "failed_task_ids": [str(task.id) for task in failed]}
        created = _create_compensations(db, graph, nodes)
        if created == 0:
            graph.status = "failed"
            graph.completed_at = stamp
        append_event(db, graph, "graph_failed_closed", "task-graph-controller", {**graph.terminal_reason, "compensation_tasks_created": created})
        return transitioned, created
    if tasks and all(task.status == "succeeded" for task in tasks):
        graph.status = "succeeded"
        graph.completed_at = stamp
        append_event(db, graph, "graph_succeeded", "task-graph-controller", {"attempts": attempts})
    elif graph.status == "cancelling" and all(task.status in TERMINAL_TASK for task in tasks):
        created = _create_compensations(db, graph, nodes)
        graph.status = "compensating" if created else "cancelled"
        graph.completed_at = None if created else stamp
        return transitioned, created
    else:
        active = [task for task in tasks if task.status in {"queued", "pending_approval", "leased", "running"}]
        if not active and tasks:
            graph.status = "failed"
            graph.completed_at = stamp
            graph.terminal_reason = {"category": "deadlock", "reason": "No runnable or terminal path remains."}
            append_event(db, graph, "graph_deadlocked", "task-graph-controller", graph.terminal_reason)
    return transitioned, 0


def serialize_graph(db: Session, graph: TaskGraph) -> dict:
    nodes = db.scalars(select(TaskGraphNode).where(TaskGraphNode.graph_id == graph.id).order_by(TaskGraphNode.ordinal)).all()
    messages = db.scalars(select(TaskGraphMessage).where(TaskGraphMessage.graph_id == graph.id).order_by(TaskGraphMessage.sequence)).all()
    events = db.scalars(select(TaskGraphEvent).where(TaskGraphEvent.graph_id == graph.id).order_by(TaskGraphEvent.sequence)).all()
    return {
        "id": graph.id, "graph_key": graph.graph_key, "project": graph.project, "objective": graph.objective,
        "status": graph.status, "schema_version": graph.schema_version, "manifest_digest": graph.manifest_digest,
        "max_nodes": graph.max_nodes, "max_total_attempts": graph.max_total_attempts,
        "max_duration_seconds": graph.max_duration_seconds, "max_parallelism": graph.max_parallelism,
        "terminal_reason": graph.terminal_reason, "created_at": graph.created_at, "activated_at": graph.activated_at,
        "deadline_at": graph.deadline_at, "completed_at": graph.completed_at,
        "nodes": [{"id": str(n.id), "key": n.node_key, "role": n.role, "type": n.node_type, "status": n.status, "task_id": str(n.task_id) if n.task_id else None, "depends_on": n.depends_on, "input_type": n.input_type, "output_type": n.output_type, "stop_conditions": n.stop_conditions, "compensation_declared": bool(n.compensation)} for n in nodes],
        "messages": [{"sequence": m.sequence, "node_id": str(m.node_id) if m.node_id else None, "message_type": m.message_type, "sender": m.sender, "recipient": m.recipient, "payload": m.payload, "payload_digest": m.payload_digest, "created_at": m.created_at} for m in messages],
        "events": [{"sequence": e.sequence, "event_type": e.event_type, "actor": e.actor, "payload": e.payload, "previous_digest": e.previous_digest, "event_digest": e.event_digest, "created_at": e.created_at} for e in events],
    }
