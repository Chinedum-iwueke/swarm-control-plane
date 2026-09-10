from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_agent
from app.db.session import get_db
from app.models import Agent, EngineeringMission
from app.schemas import (
    BrokerTicketRequest,
    BrokerTicketResponse,
    TaskCompleteRequest,
    TaskEventResponse,
    TaskExecutionHeartbeatRequest,
    TaskFailRequest,
    TaskLeaseRequest,
    TaskLeaseResponse,
    TaskMutationResponse,
    TaskReleaseRequest,
    TaskResponse,
    TaskStartRequest,
)
from app.services.broker_tickets import issue_broker_ticket
from app.services.controls import matching_control_scopes
from app.services.governance import rearm_task_approval
from app.services.missions import refresh_mission
from app.services.tasks import (
    append_task_event,
    clear_lease,
    lease_next_task,
    lock_task,
    serialize_task,
    verify_task_lease,
)

router = APIRouter(
    prefix="/v1/agent/tasks",
    tags=["agent-task-runtime"],
)


def _reconcile_task_graph(db: Session, task) -> None:
    if task.task_graph_node_id is None:
        return
    from app.models import TaskGraph, TaskGraphNode
    from app.services.task_graphs import reconcile_graph

    node = db.get(TaskGraphNode, task.task_graph_node_id)
    graph = db.get(TaskGraph, node.graph_id) if node is not None else None
    if graph is not None:
        reconcile_graph(db, graph)


def _record_graph_task_message(db: Session, task, *, succeeded: bool) -> None:
    if task.task_graph_node_id is None:
        return
    from app.models import TaskGraph, TaskGraphNode
    from app.schemas.task_graph import TaskGraphMessageCreate
    from app.services.task_graphs import append_message

    node = db.get(TaskGraphNode, task.task_graph_node_id)
    graph = db.get(TaskGraph, node.graph_id) if node is not None else None
    if graph is None:
        return
    append_message(
        db,
        graph,
        TaskGraphMessageCreate(
            node_key=node.node_key,
            message_type=node.output_type if succeeded else "failure.report",
            sender=node.role,
            recipient="task-graph-controller",
            payload=task.result if succeeded else task.failure,
        ),
    )


def _append_terminal_event(
    db: Session,
    task,
    event_type: str,
    message: str,
    *,
    agent_id: uuid.UUID,
    payload: dict,
):
    from app.services.agent_context import discard_working_memory

    discarded = discard_working_memory(db, task.id)
    return append_task_event(
        db,
        task,
        event_type,
        message,
        agent_id=agent_id,
        payload={**payload, "working_memory_discarded": discarded},
    )


@router.post(
    "/{task_id}/broker-ticket",
    response_model=BrokerTicketResponse,
)
def get_broker_ticket(
    task_id: uuid.UUID,
    payload: BrokerTicketRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> BrokerTicketResponse:
    task = lock_task(db, task_id)
    verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"running"},
    )
    ticket = issue_broker_ticket(
        db,
        task,
        agent,
        secret=get_settings().infrastructure_broker_secret,
    )
    append_task_event(
        db,
        task,
        "broker_ticket_issued",
        "Issued a bounded infrastructure broker ticket.",
        agent_id=agent.id,
        payload={
            "operation": ticket.payload.contract.operation,
            "expires_at": ticket.payload.expires_at.isoformat(),
        },
    )
    db.commit()
    return ticket


@router.post(
    "/lease",
    response_model=TaskLeaseResponse,
)
def lease_task(
    payload: TaskLeaseRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskLeaseResponse:
    paused_scopes = matching_control_scopes(db, agent)
    if paused_scopes:
        db.rollback()
        return TaskLeaseResponse(
            task=None,
            lease_token=None,
            paused=True,
            pause_reasons=[
                scope.reason or "Paused by operator." for scope in paused_scopes
            ],
        )
    task, raw_token, _ = lease_next_task(
        db,
        agent,
        payload.lease_seconds,
    )

    if task is None:
        # Approval expiry is reconciled before selection. Persist it even when
        # no eligible task remains, or an expired approval stays queued forever.
        db.commit()

        return TaskLeaseResponse(
            task=None,
            lease_token=None,
        )

    db.commit()
    db.refresh(task)

    return TaskLeaseResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        lease_token=raw_token,
    )


@router.post(
    "/{task_id}/start",
    response_model=TaskMutationResponse,
)
def start_task(
    task_id: uuid.UUID,
    payload: TaskStartRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = lock_task(db, task_id)

    now = verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"leased"},
    )

    task.status = "running"
    if task.task_type == "founder_request":
        from app.services.conversations import record_planning_started

        record_planning_started(db, task)
    task.started_at = task.started_at or now
    task.last_execution_heartbeat_at = now

    event = append_task_event(
        db,
        task,
        "task_started",
        payload.message,
        agent_id=agent.id,
        payload={},
    )

    db.commit()
    db.refresh(task)
    db.refresh(event)

    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )


@router.post(
    "/{task_id}/heartbeat",
    response_model=TaskMutationResponse,
)
def heartbeat_task(
    task_id: uuid.UUID,
    payload: TaskExecutionHeartbeatRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = lock_task(db, task_id)

    now = verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"leased", "running"},
    )

    task.last_execution_heartbeat_at = now
    task.lease_expires_at = now + timedelta(seconds=payload.lease_seconds)

    event = append_task_event(
        db,
        task,
        "task_heartbeat",
        payload.message,
        agent_id=agent.id,
        payload={
            "progress": payload.progress,
            "lease_expires_at": (task.lease_expires_at.isoformat()),
        },
    )

    db.commit()
    db.refresh(task)
    db.refresh(event)

    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )


@router.post(
    "/{task_id}/complete",
    response_model=TaskMutationResponse,
)
def complete_task(
    task_id: uuid.UUID,
    payload: TaskCompleteRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = lock_task(db, task_id)

    now = verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"running"},
    )
    if task.cancel_requested_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Task graph cancellation is pending; completion is no longer accepted.",
        )

    task.status = "succeeded"
    task.result = payload.result
    task.failure = {}
    task.completed_at = now

    event = _append_terminal_event(
        db,
        task,
        "task_completed",
        payload.message,
        agent_id=agent.id,
        payload={
            "result": payload.result,
        },
    )
    _record_graph_task_message(db, task, succeeded=True)
    clear_lease(task)
    if task.mission_id is not None:
        refresh_mission(db, task.mission_id)
    _reconcile_task_graph(db, task)

    db.commit()
    db.refresh(task)
    db.refresh(event)

    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )


@router.post(
    "/{task_id}/fail",
    response_model=TaskMutationResponse,
)
def fail_task(
    task_id: uuid.UUID,
    payload: TaskFailRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = lock_task(db, task_id)

    now = verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"leased", "running"},
    )

    previous_agent_id = task.assigned_agent_id
    failure_payload = {
        **payload.failure,
        "retryable": payload.retryable,
    }

    task.failure = failure_payload

    event = _append_terminal_event(
        db,
        task,
        "task_failed",
        payload.message,
        agent_id=agent.id,
        payload=failure_payload,
    )

    mission = (
        db.get(EngineeringMission, task.mission_id)
        if task.mission_id is not None
        else None
    )
    supervised = mission is not None and mission.supervision_enabled
    if payload.retryable and task.attempt_count < task.max_attempts and not supervised:
        task.status = "queued"

        append_task_event(
            db,
            task,
            "task_requeued",
            "Task requeued after retryable failure.",
            agent_id=previous_agent_id,
            payload={},
        )
    else:
        task.status = "failed"
        task.completed_at = now

    _record_graph_task_message(db, task, succeeded=False)
    clear_lease(task)
    if task.mission_id is not None:
        refresh_mission(db, task.mission_id)
    _reconcile_task_graph(db, task)

    db.commit()
    db.refresh(task)
    db.refresh(event)

    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )


@router.post(
    "/{task_id}/release",
    response_model=TaskMutationResponse,
)
def release_task(
    task_id: uuid.UUID,
    payload: TaskReleaseRequest,
    agent: Annotated[Agent, Depends(get_current_agent)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskMutationResponse:
    task = lock_task(db, task_id)

    now = verify_task_lease(
        task,
        agent,
        payload.lease_token,
        allowed_statuses={"leased", "running"},
    )

    previous_status = task.status
    if task.cancel_requested_at is not None:
        task.status = "cancelled"
        task.completed_at = now
    else:
        task.status = "queued" if task.attempt_count < task.max_attempts else "failed"
    if task.status == "queued":
        rearm_task_approval(db, task, "A new approval is required after lease release.")

    if task.status == "failed":
        task.failure = {
            "reason": "lease_released",
            "message": ("Maximum attempts reached when lease was released."),
        }
        task.completed_at = now

    event = _append_terminal_event(
        db,
        task,
        "task_released",
        payload.message,
        agent_id=agent.id,
        payload={
            "previous_status": previous_status,
            "resulting_status": task.status,
        },
    )

    if task.status in {"queued", "pending_approval"}:
        append_task_event(
            db,
            task,
            "task_requeued",
            "Task requeued after lease release.",
            agent_id=agent.id,
            payload={},
        )

    clear_lease(task)
    _reconcile_task_graph(db, task)

    db.commit()
    db.refresh(task)
    db.refresh(event)

    return TaskMutationResponse(
        task=TaskResponse.model_validate(serialize_task(task)),
        event=TaskEventResponse.model_validate(event),
    )
