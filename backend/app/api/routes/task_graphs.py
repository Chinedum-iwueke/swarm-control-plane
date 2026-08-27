import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.task_graph import TaskGraph
from app.schemas.task_graph import (
    TaskGraphAction,
    TaskGraphCreate,
    TaskGraphMessageCreate,
    TaskGraphReconcileResponse,
    TaskGraphResponse,
)
from app.services.task_graphs import (
    activate_graph,
    append_message,
    cancel_graph,
    create_graph,
    reconcile_graph,
    serialize_graph,
)

router = APIRouter(prefix="/v1/task-graphs", tags=["typed-task-graphs"], dependencies=[Depends(require_orchestrator)])


def locked(db: Session, graph_id: uuid.UUID) -> TaskGraph:
    graph = db.scalar(select(TaskGraph).where(TaskGraph.id == graph_id).with_for_update())
    if graph is None:
        raise HTTPException(404, "Task graph not found.")
    return graph


@router.post("", response_model=TaskGraphResponse, status_code=status.HTTP_201_CREATED)
def create(payload: TaskGraphCreate, db: Annotated[Session, Depends(get_db)]) -> TaskGraphResponse:
    try:
        graph = create_graph(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Task graph key or manifest digest already exists.") from exc
    db.refresh(graph)
    return TaskGraphResponse.model_validate(serialize_graph(db, graph))


@router.get("", response_model=list[TaskGraphResponse])
def list_graphs(db: Annotated[Session, Depends(get_db)], limit: Annotated[int, Query(ge=1, le=100)] = 50) -> list[TaskGraphResponse]:
    graphs = db.scalars(select(TaskGraph).order_by(TaskGraph.created_at.desc()).limit(limit)).all()
    return [TaskGraphResponse.model_validate(serialize_graph(db, graph)) for graph in graphs]


@router.get("/{graph_id}", response_model=TaskGraphResponse)
def get(graph_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> TaskGraphResponse:
    graph = db.get(TaskGraph, graph_id)
    if graph is None:
        raise HTTPException(404, "Task graph not found.")
    return TaskGraphResponse.model_validate(serialize_graph(db, graph))


@router.post("/{graph_id}/activate", response_model=TaskGraphResponse)
def activate(graph_id: uuid.UUID, payload: TaskGraphAction, db: Annotated[Session, Depends(get_db)]) -> TaskGraphResponse:
    graph = locked(db, graph_id)
    activate_graph(db, graph, payload.actor)
    db.commit()
    db.refresh(graph)
    return TaskGraphResponse.model_validate(serialize_graph(db, graph))


@router.post("/{graph_id}/messages", response_model=TaskGraphResponse)
def message(graph_id: uuid.UUID, payload: TaskGraphMessageCreate, db: Annotated[Session, Depends(get_db)]) -> TaskGraphResponse:
    graph = locked(db, graph_id)
    append_message(db, graph, payload)
    db.commit()
    db.refresh(graph)
    return TaskGraphResponse.model_validate(serialize_graph(db, graph))


@router.post("/{graph_id}/cancel", response_model=TaskGraphReconcileResponse)
def cancel(graph_id: uuid.UUID, payload: TaskGraphAction, db: Annotated[Session, Depends(get_db)]) -> TaskGraphReconcileResponse:
    graph = locked(db, graph_id)
    transitioned = cancel_graph(db, graph, payload.actor, payload.reason)
    _, compensations = reconcile_graph(db, graph)
    db.commit()
    db.refresh(graph)
    return TaskGraphReconcileResponse(graph=TaskGraphResponse.model_validate(serialize_graph(db, graph)), transitioned_nodes=transitioned, compensation_tasks_created=compensations)


@router.post("/{graph_id}/reconcile", response_model=TaskGraphReconcileResponse)
def reconcile(graph_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]) -> TaskGraphReconcileResponse:
    graph = locked(db, graph_id)
    transitioned, compensations = reconcile_graph(db, graph)
    db.commit()
    db.refresh(graph)
    return TaskGraphReconcileResponse(graph=TaskGraphResponse.model_validate(serialize_graph(db, graph)), transitioned_nodes=transitioned, compensation_tasks_created=compensations)
