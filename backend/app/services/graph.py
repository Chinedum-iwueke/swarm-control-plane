from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from itertools import chain
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import Session

from app.models.agent_context import AgentContextManifest
from app.models.evidence import CanonicalEvidenceEdge, CanonicalEvidenceObject
from app.models.graph import (
    CognitiveToolReceipt,
    EvidenceGraphProjectionEdge,
    EvidenceGraphProjectionNode,
    EvidenceGraphProjectionState,
)
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.graph import (
    CanonicalEdgeCreate,
    CognitiveToolRequest,
    ContextPackRequest,
    GraphLandscapeRequest,
    GraphQueryRequest,
)
from app.services.evidence import EvidenceAccessContext, get_evidence_object
from app.services.lifecycle import is_active_expression
from app.services.retrieval import corpus_epoch

PROJECTION_NAME = "canonical-knowledge-graph"
PROJECTION_VERSION = "knowledge-graph-v1.0.0"
TOOL_VERSION = "deterministic-scientific-tools-v1.0.0"
_ACCESS_LEVEL = {"public": 0, "internal": 1, "restricted": 2, "protected": 3}
_TYPE_RULES: dict[str, set[tuple[str, str]]] = {
    "supports": {
        ("scientific_object", "claim"),
        ("result", "claim"),
        ("claim", "belief"),
    },
    "contradicts": {
        ("scientific_object", "claim"),
        ("result", "claim"),
        ("claim", "claim"),
    },
    "uses_method": {("run", "method"), ("hypothesis", "method")},
    "uses_dataset": {
        ("run", "dataset"),
        ("method", "dataset"),
        ("hypothesis", "dataset"),
    },
    "produced_result": {("run", "result")},
    "reviews": {
        ("review", "claim"),
        ("review", "hypothesis"),
        ("review", "method"),
        ("review", "run"),
        ("review", "result"),
    },
    "decides_on": {
        ("decision", "result"),
        ("decision", "claim"),
        ("decision", "belief"),
    },
    "belongs_to_trial_family": {
        ("run", "claim"),
        ("result", "claim"),
        ("run", "hypothesis"),
        ("result", "hypothesis"),
    },
    "depends_on": {
        ("claim", "assumption"),
        ("method", "assumption"),
        ("belief", "belief"),
    },
    "cites": {("claim", "scientific_object"), ("method", "scientific_object")},
}
_PROJECTION_BATCH_SIZE = 2_000
_LANDSCAPE_SEMANTIC_TYPES = (
    "claim",
    "hypothesis",
    "research_candidate",
    "method",
    "assumption",
    "dataset",
    "run",
    "result",
    "review",
    "decision",
    "belief",
    "episode",
)
_LANDSCAPE_SEMANTIC_SHARE = 0.82
_EPISODE_CONTEXT_LIMIT = 20
_EPISODE_EVENT_LIMIT = 200
_EPISODE_RECEIPT_LIMIT = 100


def episode_replay(
    db: Session,
    episode_id: UUID,
    access: EvidenceAccessContext,
) -> dict[str, Any]:
    """Project an episode from explicit immutable and operational records only."""
    episode = get_evidence_object(db, episode_id, access, audit=False)
    if episode.object_type != "episode":
        raise HTTPException(
            status_code=422, detail="Replay requires an episode object."
        )
    raw_task_id = episode.payload.get("task_id")
    task_id: UUID | None = None
    if raw_task_id:
        try:
            task_id = UUID(str(raw_task_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail="Episode contains an invalid explicit task identifier.",
            ) from exc
    task = db.get(Task, task_id) if task_id else None
    if task_id and task is None:
        raise HTTPException(
            status_code=409,
            detail="Episode task identifier does not resolve to a task.",
        )
    if task is not None and task.project != episode.project:
        raise HTTPException(
            status_code=409,
            detail="Episode and task project boundaries do not match.",
        )

    manifests: list[AgentContextManifest] = []
    events: list[TaskEvent] = []
    manifest_truncated = event_truncated = False
    if task_id:
        manifests = list(
            db.scalars(
                select(AgentContextManifest)
                .where(AgentContextManifest.task_id == task_id)
                .order_by(
                    AgentContextManifest.attempt_number,
                    AgentContextManifest.created_at,
                    AgentContextManifest.id,
                )
                .limit(_EPISODE_CONTEXT_LIMIT + 1)
            ).all()
        )
        manifest_truncated = len(manifests) > _EPISODE_CONTEXT_LIMIT
        manifests = manifests[:_EPISODE_CONTEXT_LIMIT]
        events = list(
            db.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id)
                .order_by(TaskEvent.created_at, TaskEvent.id)
                .limit(_EPISODE_EVENT_LIMIT + 1)
            ).all()
        )
        event_truncated = len(events) > _EPISODE_EVENT_LIMIT
        events = events[:_EPISODE_EVENT_LIMIT]

    references: list[dict[str, Any]] = []
    documents: list[tuple[str, Any]] = [("episode", episode.payload)]
    if task is not None:
        documents.extend([("task.result", task.result), ("task.failure", task.failure)])
    documents.extend((f"event.{item.id}", item.payload) for item in events)
    for source, document in documents:
        references.extend(_explicit_receipt_references(document, source))
    references = _deduplicate_receipt_references(references)
    receipt_truncated = len(references) > _EPISODE_RECEIPT_LIMIT
    references = references[:_EPISODE_RECEIPT_LIMIT]
    registered_ids = (
        {
            str(item)
            for item in db.scalars(
                select(QuantitativeProducerReceipt.id).where(
                    QuantitativeProducerReceipt.id.in_(
                        [
                            UUID(item["receipt_id"])
                            for item in references
                            if item.get("receipt_id")
                        ]
                    )
                )
            ).all()
        }
        if any(item.get("receipt_id") for item in references)
        else set()
    )
    registered_digests = (
        {
            item
            for item in db.scalars(
                select(QuantitativeProducerReceipt.receipt_digest).where(
                    QuantitativeProducerReceipt.receipt_digest.in_(
                        [
                            item["receipt_digest"]
                            for item in references
                            if item.get("receipt_digest")
                        ]
                    )
                )
            ).all()
        }
        if any(item.get("receipt_digest") for item in references)
        else set()
    )
    for item in references:
        item["registered"] = bool(
            item.get("receipt_id") in registered_ids
            or item.get("receipt_digest") in registered_digests
        )

    truncation_reasons = []
    if manifest_truncated:
        truncation_reasons.append("context_manifests")
    if event_truncated:
        truncation_reasons.append("task_events")
    if receipt_truncated:
        truncation_reasons.append("receipts")
    return {
        "schema_version": "episode-replay-v1.0.0",
        "episode_id": episode.id,
        "episode_digest": episode.content_digest,
        "project": episode.project,
        "task": _episode_task(task) if task else None,
        "context_manifests": [_episode_manifest(item) for item in manifests],
        "task_events": [_episode_event(item) for item in events],
        "receipts": references,
        "bounded": bool(truncation_reasons),
        "truncation_reasons": truncation_reasons,
        "narrative_policy": "explicit-records-only",
    }


def _episode_task(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "task_number": task.task_number,
        "task_type": task.task_type,
        "title": task.title,
        "status": task.status,
        "attempt_count": task.attempt_count,
        "plan_digest": task.plan_digest,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


def _episode_manifest(item: AgentContextManifest) -> dict[str, Any]:
    return {
        "id": item.id,
        "agent_id": item.agent_id,
        "attempt_number": item.attempt_number,
        "purpose": item.purpose,
        "manifest_digest": item.manifest_digest,
        "context_pack_digest": item.context_pack_digest,
        "item_count": item.item_count,
        "status": item.status,
        "created_at": item.created_at,
    }


def _episode_event(item: TaskEvent) -> dict[str, Any]:
    return {
        "id": item.id,
        "event_type": item.event_type,
        "attempt_number": item.attempt_number,
        "agent_id": item.agent_id,
        "message": item.message,
        "payload": item.payload,
        "created_at": item.created_at,
    }


def _explicit_receipt_references(value: Any, source: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        receipt_id = value.get("receipt_id")
        receipt_digest = value.get("receipt_digest")
        receipt_path = value.get("receipt_path")
        valid_id = None
        if receipt_id:
            try:
                valid_id = str(UUID(str(receipt_id)))
            except ValueError:
                valid_id = None
        valid_digest = (
            str(receipt_digest)
            if isinstance(receipt_digest, str)
            and len(receipt_digest) == 64
            and all(char in "0123456789abcdef" for char in receipt_digest)
            else None
        )
        valid_path = str(receipt_path) if isinstance(receipt_path, str) else None
        if valid_id or valid_digest or valid_path:
            found.append(
                {
                    "source": source,
                    "receipt_id": valid_id,
                    "receipt_digest": valid_digest,
                    "receipt_path": valid_path,
                }
            )
        for key, child in value.items():
            found.extend(_explicit_receipt_references(child, f"{source}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_explicit_receipt_references(child, f"{source}[{index}]"))
    return found


def _deduplicate_receipt_references(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = (
            item.get("receipt_id"),
            item.get("receipt_digest"),
            item.get("receipt_path"),
        )
        unique.setdefault(key, item)
    return list(unique.values())


def _stream_digest(
    rows,
    progress: Callable[[str, int, int, str], None] | None = None,
    total: int = 0,
) -> str:
    digest = hashlib.sha256()
    processed = 0
    for processed, row in enumerate(rows, start=1):
        encoded = _canonical(row)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        if progress is not None and processed % _PROJECTION_BATCH_SIZE == 0:
            progress("digest-corpus", processed, total or processed, "records")
    if progress is not None:
        progress("digest-corpus", processed, total or max(processed, 1), "records")
    return digest.hexdigest()


def digest_document(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def register_edge(
    db: Session,
    payload: CanonicalEdgeCreate,
    access: EvidenceAccessContext,
    *,
    commit: bool = True,
) -> CanonicalEvidenceEdge:
    if not access.may_write:
        raise HTTPException(status_code=403, detail="Canonical edge write denied.")
    subject = get_evidence_object(db, payload.subject_id, access, audit=False)
    target = get_evidence_object(db, payload.object_id, access, audit=False)
    provenance = get_evidence_object(
        db, payload.provenance_object_id, access, audit=False
    )
    _validate_edge_types(payload.predicate, subject.object_type, target.object_type)
    required_access = max(
        _ACCESS_LEVEL[subject.access_class],
        _ACCESS_LEVEL[target.access_class],
        _ACCESS_LEVEL[provenance.access_class],
    )
    if _ACCESS_LEVEL[payload.access_class] < required_access:
        raise HTTPException(
            status_code=422,
            detail="Edge access class cannot expose a protected endpoint or provenance.",
        )
    material = payload.model_dump(mode="json")
    record_digest = digest_document(material)
    existing = db.scalar(
        select(CanonicalEvidenceEdge).where(
            CanonicalEvidenceEdge.record_digest == record_digest
        )
    )
    if existing is not None:
        return existing
    identity_conflict = db.scalar(
        select(CanonicalEvidenceEdge).where(
            CanonicalEvidenceEdge.subject_id == payload.subject_id,
            CanonicalEvidenceEdge.predicate == payload.predicate,
            CanonicalEvidenceEdge.object_id == payload.object_id,
        )
    )
    if identity_conflict is not None:
        raise HTTPException(
            status_code=409, detail="Canonical edge identity is immutable."
        )
    record = CanonicalEvidenceEdge(
        subject_id=payload.subject_id,
        predicate=payload.predicate,
        object_id=payload.object_id,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        provenance_object_id=payload.provenance_object_id,
        access_class=payload.access_class,
        record_digest=record_digest,
    )
    db.add(record)
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def graph_corpus_digest(
    db: Session,
    progress: Callable[[str, int, int, str], None] | None = None,
    total: int = 0,
) -> str:
    active_ids = select(CanonicalEvidenceObject.id).where(is_active_expression())
    objects = db.execute(
        select(
            CanonicalEvidenceObject.id,
            CanonicalEvidenceObject.content_digest,
            CanonicalEvidenceObject.object_type,
            CanonicalEvidenceObject.project,
            CanonicalEvidenceObject.access_class,
        )
        .where(is_active_expression())
        .order_by(CanonicalEvidenceObject.id)
    ).yield_per(_PROJECTION_BATCH_SIZE)
    edges = db.execute(
        select(
            CanonicalEvidenceEdge.id,
            CanonicalEvidenceEdge.subject_id,
            CanonicalEvidenceEdge.predicate,
            CanonicalEvidenceEdge.object_id,
            CanonicalEvidenceEdge.valid_from,
            CanonicalEvidenceEdge.valid_until,
            CanonicalEvidenceEdge.provenance_object_id,
            CanonicalEvidenceEdge.access_class,
            CanonicalEvidenceEdge.record_digest,
        )
        .where(
            CanonicalEvidenceEdge.subject_id.in_(active_ids),
            CanonicalEvidenceEdge.object_id.in_(active_ids),
        )
        .order_by(
            CanonicalEvidenceEdge.subject_id,
            CanonicalEvidenceEdge.predicate,
            CanonicalEvidenceEdge.object_id,
        )
    ).yield_per(_PROJECTION_BATCH_SIZE)
    return _stream_digest(
        chain(
            [("version", PROJECTION_VERSION)],
            (
                (
                    "object",
                    str(row.id),
                    row.content_digest,
                    row.object_type,
                    row.project,
                    row.access_class,
                )
                for row in objects
            ),
            (
                (
                    "edge",
                    str(row.id),
                    str(row.subject_id),
                    row.predicate,
                    str(row.object_id),
                    row.valid_from.isoformat() if row.valid_from else None,
                    row.valid_until.isoformat() if row.valid_until else None,
                    str(row.provenance_object_id) if row.provenance_object_id else None,
                    row.access_class,
                    row.record_digest,
                )
                for row in edges
            ),
        ),
        progress=progress,
        total=total,
    )


def build_graph_projection(
    db: Session,
    progress: Callable[[str, int, int, str], None] | None = None,
) -> EvidenceGraphProjectionState:
    source_epoch = corpus_epoch(db)
    total_nodes = int(
        db.scalar(
            select(func.count())
            .select_from(CanonicalEvidenceObject)
            .where(is_active_expression())
        )
        or 0
    )
    total_edges = int(
        db.scalar(
            select(func.count())
            .select_from(CanonicalEvidenceEdge)
            .where(
                CanonicalEvidenceEdge.subject_id.in_(
                    select(CanonicalEvidenceObject.id).where(is_active_expression())
                ),
                CanonicalEvidenceEdge.object_id.in_(
                    select(CanonicalEvidenceObject.id).where(is_active_expression())
                ),
            )
        )
        or 0
    )
    corpus = graph_corpus_digest(
        db,
        progress=progress,
        total=1 + total_nodes + total_edges,
    )
    db.execute(delete(EvidenceGraphProjectionEdge))
    db.execute(delete(EvidenceGraphProjectionNode))
    db.execute(delete(EvidenceGraphProjectionState))
    node_count = 0
    last_object_id: UUID | None = None
    while True:
        statement = (
            select(CanonicalEvidenceObject)
            .where(is_active_expression())
            .order_by(CanonicalEvidenceObject.id)
            .limit(_PROJECTION_BATCH_SIZE)
        )
        if last_object_id is not None:
            statement = statement.where(CanonicalEvidenceObject.id > last_object_id)
        objects = list(db.scalars(statement).all())
        if not objects:
            break
        last_object_id = objects[-1].id
        db.execute(
            insert(EvidenceGraphProjectionNode),
            [
                {
                    "object_id": item.id,
                    "object_type": item.object_type,
                    "project": item.project,
                    "access_class": item.access_class,
                    "content_digest": item.content_digest,
                    "label": _object_label(item),
                    "projection_version": PROJECTION_VERSION,
                }
                for item in objects
            ],
        )
        node_count += len(objects)
        if progress is not None:
            progress(
                "project-nodes", min(node_count, total_nodes), total_nodes or 1, "nodes"
            )
        db.expunge_all()

    edge_count = 0
    last_edge_id: UUID | None = None
    while True:
        statement = (
            select(CanonicalEvidenceEdge)
            .where(
                CanonicalEvidenceEdge.subject_id.in_(
                    select(CanonicalEvidenceObject.id).where(is_active_expression())
                ),
                CanonicalEvidenceEdge.object_id.in_(
                    select(CanonicalEvidenceObject.id).where(is_active_expression())
                ),
            )
            .order_by(CanonicalEvidenceEdge.id)
            .limit(_PROJECTION_BATCH_SIZE)
        )
        if last_edge_id is not None:
            statement = statement.where(CanonicalEvidenceEdge.id > last_edge_id)
        edges = list(db.scalars(statement).all())
        if not edges:
            break
        last_edge_id = edges[-1].id
        db.execute(
            insert(EvidenceGraphProjectionEdge),
            [
                {
                    "edge_id": edge.id,
                    "subject_id": edge.subject_id,
                    "predicate": edge.predicate,
                    "object_id": edge.object_id,
                    "valid_from": edge.valid_from,
                    "valid_until": edge.valid_until,
                    "provenance_object_id": edge.provenance_object_id
                    or edge.subject_id,
                    "access_class": edge.access_class or "internal",
                    "record_digest": _edge_digest(edge),
                    "projection_version": PROJECTION_VERSION,
                }
                for edge in edges
            ],
        )
        edge_count += len(edges)
        if progress is not None:
            progress(
                "project-edges", min(edge_count, total_edges), total_edges or 1, "edges"
            )
        db.expunge_all()
    manifest = {
        "schema_version": "knowledge-graph-manifest-v1.1.0",
        "projection_version": PROJECTION_VERSION,
        "corpus_digest": corpus,
        "node_count": node_count,
        "edge_count": edge_count,
    }
    state = EvidenceGraphProjectionState(
        projection_name=PROJECTION_NAME,
        projection_version=PROJECTION_VERSION,
        corpus_digest=corpus,
        source_epoch=source_epoch,
        node_count=node_count,
        edge_count=edge_count,
        manifest=manifest,
        manifest_digest=digest_document(manifest),
        built_at=datetime.now(UTC),
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def update_graph_projection_incrementally(
    db: Session,
    changed_object_ids: set[UUID],
    *,
    expected_epoch: int,
) -> EvidenceGraphProjectionState:
    state = db.get(EvidenceGraphProjectionState, PROJECTION_NAME)
    source_epoch = corpus_epoch(db)
    if state is None or source_epoch != expected_epoch:
        raise HTTPException(status_code=409, detail="Incremental graph snapshot moved.")
    impacted = set(changed_object_ids)
    if impacted:
        db.execute(
            delete(EvidenceGraphProjectionEdge).where(
                or_(
                    EvidenceGraphProjectionEdge.subject_id.in_(impacted),
                    EvidenceGraphProjectionEdge.object_id.in_(impacted),
                    EvidenceGraphProjectionEdge.provenance_object_id.in_(impacted),
                )
            )
        )
        db.execute(
            delete(EvidenceGraphProjectionNode).where(
                EvidenceGraphProjectionNode.object_id.in_(impacted)
            )
        )
        objects = list(
            db.scalars(
                select(CanonicalEvidenceObject).where(
                    CanonicalEvidenceObject.id.in_(impacted),
                    is_active_expression(),
                )
            ).all()
        )
        if objects:
            db.execute(
                insert(EvidenceGraphProjectionNode),
                [
                    {
                        "object_id": item.id,
                        "object_type": item.object_type,
                        "project": item.project,
                        "access_class": item.access_class,
                        "content_digest": item.content_digest,
                        "label": _object_label(item),
                        "projection_version": PROJECTION_VERSION,
                    }
                    for item in objects
                ],
            )
        active_ids = select(CanonicalEvidenceObject.id).where(is_active_expression())
        edges = list(
            db.scalars(
                select(CanonicalEvidenceEdge).where(
                    or_(
                        CanonicalEvidenceEdge.subject_id.in_(impacted),
                        CanonicalEvidenceEdge.object_id.in_(impacted),
                        CanonicalEvidenceEdge.provenance_object_id.in_(impacted),
                    ),
                    CanonicalEvidenceEdge.subject_id.in_(active_ids),
                    CanonicalEvidenceEdge.object_id.in_(active_ids),
                )
            ).all()
        )
        if edges:
            db.execute(
                insert(EvidenceGraphProjectionEdge),
                [
                    {
                        "edge_id": edge.id,
                        "subject_id": edge.subject_id,
                        "predicate": edge.predicate,
                        "object_id": edge.object_id,
                        "valid_from": edge.valid_from,
                        "valid_until": edge.valid_until,
                        "provenance_object_id": edge.provenance_object_id
                        or edge.subject_id,
                        "access_class": edge.access_class or "internal",
                        "record_digest": _edge_digest(edge),
                        "projection_version": PROJECTION_VERSION,
                    }
                    for edge in edges
                ],
            )
    if corpus_epoch(db) != source_epoch:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Canonical evidence changed during incremental graph update.",
        )
    corpus = graph_corpus_digest(db)
    node_count = int(
        db.scalar(select(func.count()).select_from(EvidenceGraphProjectionNode)) or 0
    )
    edge_count = int(
        db.scalar(select(func.count()).select_from(EvidenceGraphProjectionEdge)) or 0
    )
    manifest = {
        "schema_version": "knowledge-graph-manifest-v1.1.0",
        "projection_version": PROJECTION_VERSION,
        "corpus_digest": corpus,
        "node_count": node_count,
        "edge_count": edge_count,
    }
    state.corpus_digest = corpus
    state.source_epoch = source_epoch
    state.node_count = node_count
    state.edge_count = edge_count
    state.manifest = manifest
    state.manifest_digest = digest_document(manifest)
    state.built_at = datetime.now(UTC)
    db.commit()
    db.refresh(state)
    return state


def graph_projection_status(
    db: Session,
) -> tuple[EvidenceGraphProjectionState, bool]:
    state = db.get(EvidenceGraphProjectionState, PROJECTION_NAME)
    if state is None:
        raise HTTPException(
            status_code=409, detail="Knowledge graph projection is not built."
        )
    current_epoch = corpus_epoch(db)
    if state.source_epoch == 0:
        stale = state.corpus_digest != graph_corpus_digest(db)
        if not stale:
            state.source_epoch = current_epoch
            db.commit()
        return state, stale
    return state, state.source_epoch != current_epoch


def graph_projection_content_digest(db: Session) -> str:
    nodes = db.execute(
        select(
            EvidenceGraphProjectionNode.object_id,
            EvidenceGraphProjectionNode.object_type,
            EvidenceGraphProjectionNode.project,
            EvidenceGraphProjectionNode.access_class,
            EvidenceGraphProjectionNode.content_digest,
            EvidenceGraphProjectionNode.label,
        ).order_by(EvidenceGraphProjectionNode.object_id)
    ).yield_per(_PROJECTION_BATCH_SIZE)
    edges = db.execute(
        select(
            EvidenceGraphProjectionEdge.edge_id,
            EvidenceGraphProjectionEdge.subject_id,
            EvidenceGraphProjectionEdge.predicate,
            EvidenceGraphProjectionEdge.object_id,
            EvidenceGraphProjectionEdge.valid_from,
            EvidenceGraphProjectionEdge.valid_until,
            EvidenceGraphProjectionEdge.provenance_object_id,
            EvidenceGraphProjectionEdge.access_class,
            EvidenceGraphProjectionEdge.record_digest,
        ).order_by(EvidenceGraphProjectionEdge.edge_id)
    ).yield_per(_PROJECTION_BATCH_SIZE)
    return _stream_digest(
        chain(
            (
                (
                    "node",
                    str(row.object_id),
                    row.object_type,
                    row.project,
                    row.access_class,
                    row.content_digest,
                    row.label,
                )
                for row in nodes
            ),
            (
                (
                    "edge",
                    str(row.edge_id),
                    str(row.subject_id),
                    row.predicate,
                    str(row.object_id),
                    row.valid_from.isoformat() if row.valid_from else None,
                    row.valid_until.isoformat() if row.valid_until else None,
                    str(row.provenance_object_id),
                    row.access_class,
                    row.record_digest,
                )
                for row in edges
            ),
        )
    )


def query_graph(
    db: Session,
    request: GraphQueryRequest,
    access: EvidenceAccessContext,
) -> dict[str, Any]:
    state, stale = graph_projection_status(db)
    if stale:
        raise HTTPException(
            status_code=409,
            detail="Knowledge graph projection is stale and must be rebuilt.",
        )
    requested = set(request.root_ids)
    if request.target_id is not None:
        requested.add(request.target_id)
    initial = _authorized_node_subset(
        db, requested, access, request.project, object_types=request.object_types
    )
    if set(initial) != requested:
        raise HTTPException(
            status_code=404, detail="Graph root or target is unavailable."
        )
    cursor_fingerprint = digest_document(
        {
            "corpus_digest": state.corpus_digest,
            "query": request.model_dump(mode="json", exclude={"cursor", "page_size"}),
        }
    )
    offset = _decode_graph_cursor(request.cursor, cursor_fingerprint)
    by_id = dict(initial)
    provenance_by_id: dict[UUID, EvidenceGraphProjectionNode] = {}
    edges: list[EvidenceGraphProjectionEdge] = []
    frontier = set(request.root_ids)
    depth_limited = False
    node_limit = request.max_nodes + 1
    for depth in range(request.max_depth):
        if not frontier or len(by_id) >= node_limit:
            break
        candidates = _frontier_edges(db, frontier, access, request)
        endpoint_ids = {
            node_id
            for edge in candidates
            for node_id in (edge.subject_id, edge.object_id)
        }
        provenance_ids = {
            edge.provenance_object_id
            for edge in candidates
            if edge.provenance_object_id is not None
        }
        authorized = _authorized_node_subset(
            db,
            endpoint_ids,
            access,
            request.project,
            object_types=request.object_types,
        )
        provenance = _authorized_node_subset(
            db, provenance_ids, access, request.project
        )
        authorized_ids = set(authorized)
        provenance_ids = set(provenance)
        accepted = [
            edge
            for edge in candidates
            if {edge.subject_id, edge.object_id} <= authorized_ids
            and edge.provenance_object_id in provenance_ids
        ]
        provenance_by_id.update(provenance)
        previous = set(by_id)
        for node_id in sorted(authorized, key=str):
            if len(by_id) >= node_limit and node_id not in by_id:
                break
            by_id[node_id] = authorized[node_id]
        existing_edges = {edge.edge_id for edge in edges}
        edges.extend(edge for edge in accepted if edge.edge_id not in existing_edges)
        frontier = {
            node_id
            for edge in accepted
            for node_id in (edge.subject_id, edge.object_id)
            if node_id not in previous and node_id in by_id
        }
        if depth == request.max_depth - 1 and frontier:
            depth_limited = True
    node_limited = len(by_id) > request.max_nodes
    edges = [
        edge for edge in edges if edge.subject_id in by_id and edge.object_id in by_id
    ]
    adjacency = _adjacency(edges, request.direction)
    visited, paths = _traverse(request, adjacency)
    ordered_ids = list(visited)[: request.max_nodes]
    if offset > len(ordered_ids):
        raise HTTPException(status_code=422, detail="Graph cursor is out of range.")
    page_ids = ordered_ids[offset : offset + request.page_size]
    selected_ids = set(page_ids)
    if offset:
        selected_ids.update(request.root_ids)
    selected_edges = [
        edge
        for edge in edges
        if edge.subject_id in selected_ids and edge.object_id in selected_ids
    ]
    provenance_ids = {
        edge.provenance_object_id
        for edge in selected_edges
        if edge.provenance_object_id is not None
    }
    response_nodes = {item: by_id[item] for item in selected_ids if item in by_id}
    response_nodes.update(
        {
            item: provenance_by_id[item]
            for item in provenance_ids
            if item in provenance_by_id
        }
    )
    next_offset = offset + len(page_ids)
    next_cursor = (
        _encode_graph_cursor(next_offset, cursor_fingerprint)
        if next_offset < len(ordered_ids)
        else None
    )
    reasons: list[str] = []
    if next_cursor is not None:
        reasons.append("page_size")
    if node_limited:
        reasons.append("max_nodes")
    if depth_limited:
        reasons.append("max_depth")
    document = {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "request": request.model_dump(mode="json"),
        "cursor_offset": offset,
        "node_ids": sorted(map(str, response_nodes)),
        "edge_digests": sorted(edge.record_digest for edge in selected_edges),
    }
    return {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "query_digest": digest_document(document),
        "nodes": [
            _node_response(response_nodes[item])
            for item in sorted(response_nodes, key=str)
        ],
        "edges": [_edge_response(item) for item in selected_edges],
        "paths": [path for path in paths if set(path) <= selected_ids],
        "truncated": bool(reasons),
        "page": {
            "cursor": request.cursor,
            "next_cursor": next_cursor,
            "page_size": request.page_size,
            "offset": offset,
            "returned": len(page_ids),
            "traversed": len(ordered_ids),
        },
        "truncation": {
            "truncated": bool(reasons),
            "reasons": reasons,
            "max_nodes": request.max_nodes,
            "max_depth": request.max_depth,
        },
    }


def graph_overview(
    db: Session,
    access: EvidenceAccessContext,
    *,
    project: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    state, stale = graph_projection_status(db)
    if stale:
        raise HTTPException(
            status_code=409,
            detail="Knowledge graph projection is stale and must be rebuilt.",
        )
    nodes = _authorized_nodes(db, access, project, limit=limit + 1)
    selected = nodes[:limit]
    selected_ids = {item.object_id for item in selected}
    request = (
        GraphQueryRequest(
            root_ids=[item.object_id for item in selected[:1]],
            project=project,
            max_nodes=limit,
        )
        if selected
        else None
    )
    edges = _authorized_edges(db, selected_ids, access, request) if request else []
    document = {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "project": project,
        "node_ids": sorted(map(str, selected_ids)),
        "edge_digests": sorted(item.record_digest for item in edges),
    }
    return {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "query_digest": digest_document(document),
        "nodes": [_node_response(item) for item in selected],
        "edges": [_edge_response(item) for item in edges],
        "paths": [],
        "truncated": len(nodes) > limit,
        "page": {
            "cursor": None,
            "next_cursor": None,
            "page_size": min(limit, 100),
            "offset": 0,
            "returned": len(selected),
            "traversed": len(selected),
        },
        "truncation": {
            "truncated": len(nodes) > limit,
            "reasons": ["page_size"] if len(nodes) > limit else [],
            "max_nodes": min(limit, 500),
            "max_depth": 1,
        },
    }


def graph_landscape(
    db: Session,
    request: GraphLandscapeRequest,
    access: EvidenceAccessContext,
) -> dict[str, Any]:
    """Return a deterministic, representative view of the canonical corpus.

    The landscape deliberately avoids treating paragraph-scale scientific objects as
    the institutional overview. It gives typed scientific lifecycle records priority,
    then uses the remaining budget for real source-to-edition provenance pairs.
    """
    state, stale = graph_projection_status(db)
    if stale:
        raise HTTPException(
            status_code=409,
            detail="Knowledge graph projection is stale and must be rebuilt.",
        )
    _validate_landscape_project(access, request.project)
    node_facets = _landscape_node_facets(db, access, request.project)
    edge_facets = _landscape_edge_facets(
        db, access, request.as_of, project=request.project
    )
    available_types = {item["value"]: item["count"] for item in node_facets}
    allowed_types = set(request.object_types) if request.object_types else None
    semantic_types = [
        item
        for item in _LANDSCAPE_SEMANTIC_TYPES
        if allowed_types is None or item in allowed_types
    ]
    semantic_budget = min(
        request.max_nodes,
        max(1, int(request.max_nodes * _LANDSCAPE_SEMANTIC_SHARE)),
    )
    semantic_slots = _allocate_landscape_type_slots(
        {item: available_types.get(item, 0) for item in semantic_types},
        semantic_budget,
    )
    semantic_nodes = _landscape_connected_nodes_by_type(
        db, access, request.project, semantic_slots
    )
    selected: dict[UUID, EvidenceGraphProjectionNode] = {
        item.object_id: item for item in semantic_nodes
    }
    source_nodes: list[EvidenceGraphProjectionNode] = []
    edition_nodes: list[EvidenceGraphProjectionNode] = []
    other_nodes: list[EvidenceGraphProjectionNode] = []
    source_types_allowed = allowed_types is None or bool(
        {"source", "edition"} & allowed_types
    )
    if len(selected) < request.max_nodes and source_types_allowed:
        source_nodes, edition_nodes = _landscape_source_edition_pairs(
            db,
            access,
            request.project,
            request.max_nodes - len(selected),
            include_sources=allowed_types is None or "source" in allowed_types,
            include_editions=allowed_types is None or "edition" in allowed_types,
        )
        for item in [*source_nodes, *edition_nodes]:
            selected[item.object_id] = item
    explicit_other_types = [
        item
        for item in request.object_types
        if item not in _LANDSCAPE_SEMANTIC_TYPES and item not in {"source", "edition"}
    ]
    if len(selected) < request.max_nodes and explicit_other_types:
        other_slots = _allocate_landscape_type_slots(
            {item: available_types.get(item, 0) for item in explicit_other_types},
            request.max_nodes - len(selected),
        )
        other_nodes = _landscape_nodes_by_type(db, access, request.project, other_slots)
        for item in other_nodes:
            selected[item.object_id] = item
    nodes = list(selected.values())[: request.max_nodes]
    selected_ids = {item.object_id for item in nodes}
    edges = _landscape_edges(
        db,
        selected_ids,
        access,
        project=request.project,
        predicates=request.predicates,
        as_of=request.as_of,
        limit=request.max_edges + 1,
    )
    edge_truncated = len(edges) > request.max_edges
    edges = edges[: request.max_edges]
    filtered_node_total = sum(
        count
        for object_type, count in available_types.items()
        if allowed_types is None or object_type in allowed_types
    )
    node_truncated = filtered_node_total > len(nodes)
    reasons: list[str] = []
    if node_truncated:
        reasons.append("max_nodes")
    if edge_truncated:
        reasons.append("max_edges")
    filters_applied = bool(
        request.object_types or request.predicates or request.project or request.as_of
    )
    document = {
        "schema_version": "knowledge-landscape-v1.0.0",
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "project": request.project,
        "object_types": request.object_types,
        "predicates": request.predicates,
        "as_of": request.as_of.isoformat() if request.as_of else None,
        "node_ids": [str(item.object_id) for item in nodes],
        "edge_digests": [item.record_digest for item in edges],
        "selection_strategy": "connected-semantic-landscape-v2",
    }
    return {
        "schema_version": "knowledge-landscape-v1.0.0",
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "query_digest": digest_document(document),
        "built_at": state.built_at,
        "source_epoch": state.source_epoch,
        "corpus_node_count": state.node_count,
        "corpus_edge_count": state.edge_count,
        "node_facets": node_facets,
        "edge_facets": edge_facets,
        "nodes": [_node_response(item) for item in nodes],
        "edges": [_edge_response(item) for item in edges],
        "selection": {
            "strategy": "connected-semantic-landscape-v2",
            "semantic_node_count": len(semantic_nodes),
            "source_node_count": len(source_nodes),
            "edition_node_count": len(edition_nodes),
            "other_node_count": len(other_nodes),
            "visible_node_limit": request.max_nodes,
            "visible_edge_limit": request.max_edges,
        },
        "filters_applied": filters_applied,
        "truncated": bool(reasons),
        "truncation_reasons": reasons,
    }


def _allocate_landscape_type_slots(
    counts: dict[str, int], budget: int
) -> dict[str, int]:
    """Round-robin type budgets prevent a populous type from hiding the rest."""
    slots = {item: 0 for item, count in counts.items() if count > 0}
    remaining = min(budget, sum(counts.values()))
    while remaining:
        progressed = False
        for item, count in counts.items():
            if item not in slots or slots[item] >= count:
                continue
            slots[item] += 1
            remaining -= 1
            progressed = True
            if not remaining:
                break
        if not progressed:
            break
    return slots


def _validate_landscape_project(
    access: EvidenceAccessContext, project: str | None
) -> None:
    if (
        project is not None
        and "*" not in access.projects
        and project not in access.projects
    ):
        raise HTTPException(status_code=403, detail="Graph project access denied.")


def _landscape_access_classes(access: EvidenceAccessContext) -> list[str]:
    return [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]


def _landscape_node_scope(
    statement, access: EvidenceAccessContext, project: str | None
):
    if access.max_access_class != "protected":
        statement = statement.where(
            EvidenceGraphProjectionNode.access_class.in_(
                _landscape_access_classes(access)
            )
        )
    if "*" not in access.projects:
        statement = statement.where(
            EvidenceGraphProjectionNode.project.in_(access.projects)
        )
    if project is not None:
        statement = statement.where(EvidenceGraphProjectionNode.project == project)
    return statement


def _landscape_node_facets(
    db: Session, access: EvidenceAccessContext, project: str | None
) -> list[dict[str, Any]]:
    statement = select(
        EvidenceGraphProjectionNode.object_type,
        func.count(EvidenceGraphProjectionNode.object_id),
    ).group_by(EvidenceGraphProjectionNode.object_type)
    statement = _landscape_node_scope(statement, access, project)
    return [
        {"value": object_type, "count": count}
        for object_type, count in db.execute(
            statement.order_by(EvidenceGraphProjectionNode.object_type)
        ).all()
    ]


def _landscape_edge_facets(
    db: Session,
    access: EvidenceAccessContext,
    as_of: datetime | None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    statement = select(
        EvidenceGraphProjectionEdge.predicate,
        func.count(EvidenceGraphProjectionEdge.edge_id),
    )
    if access.max_access_class != "protected":
        statement = statement.where(
            EvidenceGraphProjectionEdge.access_class.in_(
                _landscape_access_classes(access)
            )
        )
    if "*" not in access.projects or project is not None:
        authorized_nodes = select(EvidenceGraphProjectionNode.object_id)
        authorized_nodes = _landscape_node_scope(authorized_nodes, access, project)
        statement = statement.where(
            EvidenceGraphProjectionEdge.subject_id.in_(authorized_nodes),
            EvidenceGraphProjectionEdge.object_id.in_(authorized_nodes),
            EvidenceGraphProjectionEdge.provenance_object_id.in_(authorized_nodes),
        )
    statement = statement.group_by(EvidenceGraphProjectionEdge.predicate).order_by(
        EvidenceGraphProjectionEdge.predicate
    )
    if as_of is not None:
        point = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
        statement = statement.where(
            or_(
                EvidenceGraphProjectionEdge.valid_from.is_(None),
                EvidenceGraphProjectionEdge.valid_from <= point,
            ),
            or_(
                EvidenceGraphProjectionEdge.valid_until.is_(None),
                EvidenceGraphProjectionEdge.valid_until > point,
            ),
        )
    return [
        {"value": predicate, "count": count}
        for predicate, count in db.execute(statement).all()
    ]


def _landscape_nodes_by_type(
    db: Session,
    access: EvidenceAccessContext,
    project: str | None,
    slots: dict[str, int],
) -> list[EvidenceGraphProjectionNode]:
    result: list[EvidenceGraphProjectionNode] = []
    for object_type, limit in slots.items():
        statement = select(EvidenceGraphProjectionNode).where(
            EvidenceGraphProjectionNode.object_type == object_type
        )
        statement = _landscape_node_scope(statement, access, project)
        statement = statement.order_by(
            EvidenceGraphProjectionNode.label,
            EvidenceGraphProjectionNode.object_id,
        ).limit(limit)
        result.extend(db.scalars(statement).all())
    return result


def _landscape_connected_nodes_by_type(
    db: Session,
    access: EvidenceAccessContext,
    project: str | None,
    slots: dict[str, int],
) -> list[EvidenceGraphProjectionNode]:
    """Prefer recorded, connected evidence while retaining the type budget."""
    candidate_slots = {
        object_type: min(max(limit * 8, limit), 64)
        for object_type, limit in slots.items()
    }
    candidates = _landscape_nodes_by_type(db, access, project, candidate_slots)
    candidate_ids = {item.object_id for item in candidates}
    candidate_edges = _landscape_edges(
        db,
        candidate_ids,
        access,
        project=project,
        predicates=[],
        as_of=None,
        limit=1_280,
    )
    return _select_connected_landscape_nodes(candidates, candidate_edges, slots)


def _select_connected_landscape_nodes(
    candidates: list[EvidenceGraphProjectionNode],
    edges: list[EvidenceGraphProjectionEdge],
    slots: dict[str, int],
) -> list[EvidenceGraphProjectionNode]:
    degree: dict[UUID, int] = {item.object_id: 0 for item in candidates}
    for edge in edges:
        if edge.subject_id in degree:
            degree[edge.subject_id] += 1
        if edge.object_id in degree:
            degree[edge.object_id] += 1
    by_type: dict[str, list[EvidenceGraphProjectionNode]] = {}
    for item in candidates:
        by_type.setdefault(item.object_type, []).append(item)
    selected: list[EvidenceGraphProjectionNode] = []
    for object_type, limit in slots.items():
        ranked = sorted(
            by_type.get(object_type, []),
            key=lambda item: (
                -degree[item.object_id],
                item.label,
                str(item.object_id),
            ),
        )
        selected.extend(ranked[:limit])
    return selected


def _landscape_source_edition_pairs(
    db: Session,
    access: EvidenceAccessContext,
    project: str | None,
    budget: int,
    *,
    include_sources: bool,
    include_editions: bool,
) -> tuple[list[EvidenceGraphProjectionNode], list[EvidenceGraphProjectionNode]]:
    if budget <= 0 or not (include_sources or include_editions):
        return [], []
    source_limit = (
        budget
        if not (include_sources and include_editions)
        else max(1, (budget + 1) // 2)
    )
    statement = select(EvidenceGraphProjectionNode).where(
        EvidenceGraphProjectionNode.object_type == "source"
    )
    statement = _landscape_node_scope(statement, access, project)
    sources = list(
        db.scalars(
            statement.order_by(
                EvidenceGraphProjectionNode.label,
                EvidenceGraphProjectionNode.object_id,
            ).limit(source_limit)
        ).all()
    )
    if not include_editions or not sources:
        return (sources[:budget] if include_sources else []), []
    source_ids = {item.object_id for item in sources}
    edges = list(
        db.scalars(
            select(EvidenceGraphProjectionEdge)
            .where(
                EvidenceGraphProjectionEdge.object_id.in_(source_ids),
                EvidenceGraphProjectionEdge.predicate == "derived_from",
                EvidenceGraphProjectionEdge.access_class.in_(
                    _landscape_access_classes(access)
                ),
            )
            .order_by(EvidenceGraphProjectionEdge.edge_id)
        ).all()
    )
    edition_ids = {item.subject_id for item in edges}
    editions = _authorized_node_subset(
        db, edition_ids, access, project, object_types=["edition"]
    )
    edition_by_source: dict[UUID, EvidenceGraphProjectionNode] = {}
    for edge in edges:
        edition = editions.get(edge.subject_id)
        if edition is not None and edge.object_id not in edition_by_source:
            edition_by_source[edge.object_id] = edition
    source_result: list[EvidenceGraphProjectionNode] = []
    edition_result: list[EvidenceGraphProjectionNode] = []
    for source in sources:
        if include_sources and len(source_result) + len(edition_result) < budget:
            source_result.append(source)
        edition = edition_by_source.get(source.object_id)
        if edition is not None and len(source_result) + len(edition_result) < budget:
            edition_result.append(edition)
    return source_result, edition_result


def _landscape_edges(
    db: Session,
    node_ids: set[UUID],
    access: EvidenceAccessContext,
    *,
    project: str | None,
    predicates: list[str],
    as_of: datetime | None,
    limit: int,
) -> list[EvidenceGraphProjectionEdge]:
    if not node_ids:
        return []
    authorized_provenance = select(EvidenceGraphProjectionNode.object_id)
    authorized_provenance = _landscape_node_scope(
        authorized_provenance, access, project
    )
    statement = (
        select(EvidenceGraphProjectionEdge)
        .where(
            EvidenceGraphProjectionEdge.subject_id.in_(node_ids),
            EvidenceGraphProjectionEdge.object_id.in_(node_ids),
            EvidenceGraphProjectionEdge.provenance_object_id.in_(authorized_provenance),
            EvidenceGraphProjectionEdge.access_class.in_(
                _landscape_access_classes(access)
            ),
        )
        .order_by(
            EvidenceGraphProjectionEdge.predicate,
            EvidenceGraphProjectionEdge.edge_id,
        )
        .limit(limit)
    )
    if predicates:
        statement = statement.where(
            EvidenceGraphProjectionEdge.predicate.in_(predicates)
        )
    return [item for item in db.scalars(statement).all() if _active(item, as_of)]


def assemble_context_pack(
    db: Session,
    request: ContextPackRequest,
    access: EvidenceAccessContext,
) -> dict[str, Any]:
    graph = query_graph(
        db,
        GraphQueryRequest(
            root_ids=request.object_ids[: request.max_items],
            mode="subgraph",
            max_depth=1,
            max_nodes=request.max_items,
        ),
        access,
    )
    items = []
    for node in graph["nodes"]:
        record = get_evidence_object(db, node["id"], access, audit=False)
        text = _object_text(record)
        items.append(
            {
                "object_id": str(record.id),
                "object_type": record.object_type,
                "content_digest": record.content_digest,
                "access_class": record.access_class,
                "excerpt": text[:2000],
                "citation": {
                    "replay_path": _evidence_replay_path(record.id),
                    "coordinates": record.payload.get("coordinates"),
                },
            }
        )
    document = {
        "schema_version": "citation-context-pack-v1.0.0",
        "query": request.query,
        "purpose": request.purpose,
        "items": items,
        "graph_query_digest": graph["query_digest"],
    }
    return {**document, "context_pack_digest": digest_document(document)}


def execute_cognitive_tool(
    db: Session,
    request: CognitiveToolRequest,
    access: EvidenceAccessContext,
) -> CognitiveToolReceipt:
    if any(not math.isfinite(value) for value in request.values):
        raise HTTPException(status_code=422, detail="Tool values must be finite.")
    request_document = request.model_dump(mode="json")
    input_digest = digest_document(request_document)
    result = calculate(request.tool, request.values, request.parameters)
    output_digest = digest_document(result)
    receipt_document = {
        "tool": request.tool,
        "tool_version": TOOL_VERSION,
        "input_digest": input_digest,
        "output_digest": output_digest,
        "context_pack_digest": request.context_pack_digest,
        "actor": access.actor,
    }
    receipt_digest = digest_document(receipt_document)
    existing = db.scalar(
        select(CognitiveToolReceipt).where(
            CognitiveToolReceipt.receipt_digest == receipt_digest
        )
    )
    if existing is not None:
        return existing
    receipt = CognitiveToolReceipt(
        id=uuid.uuid4(),
        tool_name=request.tool,
        tool_version=TOOL_VERSION,
        input_digest=input_digest,
        output_digest=output_digest,
        request=request_document,
        result=result,
        context_pack_digest=request.context_pack_digest,
        actor=access.actor,
        receipt_digest=receipt_digest,
        created_at=datetime.now(UTC),
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def calculate(
    tool: str, values: list[float], parameters: dict[str, Any]
) -> dict[str, Any]:
    with localcontext() as context:
        context.prec = 28
        series = [Decimal(str(value)) for value in values]
        count = Decimal(len(series))
        mean = sum(series, Decimal(0)) / count
        if tool == "mean":
            value = mean
        elif tool == "sample-standard-deviation":
            if len(series) < 2:
                raise HTTPException(
                    status_code=422, detail="Sample deviation needs two values."
                )
            value = (sum((item - mean) ** 2 for item in series) / (count - 1)).sqrt()
        elif tool == "sharpe":
            if len(series) < 2:
                raise HTTPException(status_code=422, detail="Sharpe needs two values.")
            risk_free = Decimal(str(parameters.get("risk_free_rate", 0)))
            periods = Decimal(str(parameters.get("periods_per_year", 1)))
            excess = [item - risk_free / periods for item in series]
            excess_mean = sum(excess, Decimal(0)) / count
            deviation = (
                sum((item - excess_mean) ** 2 for item in excess) / (count - 1)
            ).sqrt()
            value = None if deviation == 0 else excess_mean / deviation * periods.sqrt()
        elif tool == "max-drawdown":
            peak = series[0]
            maximum = Decimal(0)
            for item in series:
                peak = max(peak, item)
                if peak != 0:
                    maximum = max(maximum, (peak - item) / abs(peak))
            value = maximum
        else:
            raise HTTPException(status_code=422, detail="Unknown cognitive tool.")
        return {
            "value": None if value is None else float(value),
            "observations": len(series),
            "arithmetic": "decimal-28",
        }


def _authorized_nodes(
    db: Session,
    access: EvidenceAccessContext,
    project: str | None,
    *,
    limit: int | None = None,
) -> list[EvidenceGraphProjectionNode]:
    if (
        project is not None
        and "*" not in access.projects
        and project not in access.projects
    ):
        raise HTTPException(status_code=403, detail="Graph project access denied.")
    classes = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    statement = select(EvidenceGraphProjectionNode).where(
        EvidenceGraphProjectionNode.access_class.in_(classes)
    )
    if "*" not in access.projects:
        statement = statement.where(
            EvidenceGraphProjectionNode.project.in_(access.projects)
        )
    if project is not None:
        statement = statement.where(EvidenceGraphProjectionNode.project == project)
    statement = statement.order_by(EvidenceGraphProjectionNode.object_id)
    if limit is not None:
        statement = statement.limit(limit)
    return list(db.scalars(statement).all())


def _authorized_node_subset(
    db: Session,
    node_ids: set[UUID],
    access: EvidenceAccessContext,
    project: str | None,
    *,
    object_types: list[str] | None = None,
) -> dict[UUID, EvidenceGraphProjectionNode]:
    if not node_ids:
        return {}
    if (
        project is not None
        and "*" not in access.projects
        and project not in access.projects
    ):
        raise HTTPException(status_code=403, detail="Graph project access denied.")
    classes = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    statement = select(EvidenceGraphProjectionNode).where(
        EvidenceGraphProjectionNode.object_id.in_(node_ids),
        EvidenceGraphProjectionNode.access_class.in_(classes),
    )
    if "*" not in access.projects:
        statement = statement.where(
            EvidenceGraphProjectionNode.project.in_(access.projects)
        )
    if project is not None:
        statement = statement.where(EvidenceGraphProjectionNode.project == project)
    if object_types:
        statement = statement.where(
            EvidenceGraphProjectionNode.object_type.in_(object_types)
        )
    return {item.object_id: item for item in db.scalars(statement).all()}


def _frontier_edges(
    db: Session,
    frontier: set[UUID],
    access: EvidenceAccessContext,
    request: GraphQueryRequest,
) -> list[EvidenceGraphProjectionEdge]:
    classes = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    conditions = []
    if request.direction in {"outgoing", "both"}:
        conditions.append(EvidenceGraphProjectionEdge.subject_id.in_(frontier))
    if request.direction in {"incoming", "both"}:
        conditions.append(EvidenceGraphProjectionEdge.object_id.in_(frontier))
    statement = select(EvidenceGraphProjectionEdge).where(
        or_(*conditions), EvidenceGraphProjectionEdge.access_class.in_(classes)
    )
    if request.predicates:
        statement = statement.where(
            EvidenceGraphProjectionEdge.predicate.in_(request.predicates)
        )
    statement = statement.order_by(EvidenceGraphProjectionEdge.edge_id).limit(
        request.max_nodes * 4
    )
    return [
        edge for edge in db.scalars(statement).all() if _active(edge, request.as_of)
    ]


def _authorized_edges(
    db: Session,
    node_ids: set[UUID],
    access: EvidenceAccessContext,
    request: GraphQueryRequest,
) -> list[EvidenceGraphProjectionEdge]:
    classes = [
        name
        for name, level in _ACCESS_LEVEL.items()
        if level <= _ACCESS_LEVEL[access.max_access_class]
    ]
    statement = select(EvidenceGraphProjectionEdge).where(
        EvidenceGraphProjectionEdge.subject_id.in_(node_ids),
        EvidenceGraphProjectionEdge.object_id.in_(node_ids),
        EvidenceGraphProjectionEdge.provenance_object_id.in_(node_ids),
        EvidenceGraphProjectionEdge.access_class.in_(classes),
    )
    if request.predicates:
        statement = statement.where(
            EvidenceGraphProjectionEdge.predicate.in_(request.predicates)
        )
    return [
        edge for edge in db.scalars(statement).all() if _active(edge, request.as_of)
    ]


def _active(edge: Any, as_of: datetime | None) -> bool:
    point = as_of or datetime.now(UTC)
    if point.tzinfo is None:
        point = point.replace(tzinfo=UTC)
    return not (
        (edge.valid_from is not None and point < edge.valid_from)
        or (edge.valid_until is not None and point >= edge.valid_until)
    )


def _adjacency(edges: list[Any], direction: str) -> dict[UUID, list[UUID]]:
    result: dict[UUID, list[UUID]] = {}
    for edge in edges:
        if direction in {"outgoing", "both"}:
            result.setdefault(edge.subject_id, []).append(edge.object_id)
        if direction in {"incoming", "both"}:
            result.setdefault(edge.object_id, []).append(edge.subject_id)
    for values in result.values():
        values.sort(key=str)
    return result


def _traverse(
    request: GraphQueryRequest, adjacency: dict[UUID, list[UUID]]
) -> tuple[list[UUID], list[list[UUID]]]:
    visited: list[UUID] = []
    seen: set[UUID] = set()
    paths: list[list[UUID]] = []
    queue = deque((root, [root], 0) for root in request.root_ids)
    while queue:
        node, path, depth = queue.popleft()
        if node not in seen:
            seen.add(node)
            visited.append(node)
        if request.mode == "paths" and node == request.target_id:
            paths.append(path)
            continue
        if depth >= request.max_depth:
            continue
        for neighbor in adjacency.get(node, []):
            if neighbor not in path:
                queue.append((neighbor, [*path, neighbor], depth + 1))
    return visited, paths


def _validate_edge_types(predicate: str, subject: str, target: str) -> None:
    if predicate in {"derived_from", "supersedes"}:
        return
    if (subject, target) not in _TYPE_RULES.get(predicate, set()):
        raise HTTPException(
            status_code=422,
            detail=f"Predicate {predicate} is invalid for {subject} -> {target}.",
        )


def _edge_material(edge: CanonicalEvidenceEdge) -> dict[str, Any]:
    return {
        "subject_id": str(edge.subject_id),
        "predicate": edge.predicate,
        "object_id": str(edge.object_id),
        "valid_from": edge.valid_from.isoformat() if edge.valid_from else None,
        "valid_until": edge.valid_until.isoformat() if edge.valid_until else None,
        "provenance_object_id": str(edge.provenance_object_id or edge.subject_id),
        "access_class": edge.access_class or "internal",
    }


def _edge_digest(edge: CanonicalEvidenceEdge) -> str:
    return edge.record_digest or digest_document(_edge_material(edge))


def _object_label(item: CanonicalEvidenceObject) -> str:
    payload = item.payload
    for key in (
        "title",
        "research_question",
        "proposition",
        "name",
        "statement",
        "decision",
        "content_text",
    ):
        if payload.get(key):
            return str(payload[key])[:500]
    if item.object_type == "method":
        procedure = payload.get("procedure") or {}
        if isinstance(procedure, str):
            try:
                procedure = json.loads(procedure)
            except (TypeError, ValueError):
                procedure = {}
        if isinstance(procedure, dict):
            rule = procedure.get("model_or_rule") or procedure.get("strategy")
            timeframe = procedure.get("timeframe") or procedure.get("signal_timeframe")
            universe = procedure.get("instrument_universe") or procedure.get("symbols")
            parts = [_display_token(rule)] if rule else []
            if timeframe:
                parts.append(str(timeframe))
            if isinstance(universe, list) and universe:
                symbols = ", ".join(map(str, universe[:3]))
                parts.append(f"{symbols}{' +' if len(universe) > 3 else ''}")
            if parts:
                return " · ".join(parts)[:500]
    lifecycle_fields = {
        "run": ("run_label", "attempt_number", "trial_ordinal", "status"),
        "result": ("outcome", "classification", "status"),
        "review": ("verdict", "review_kind", "status"),
        "episode": ("question", "objective", "status"),
    }
    for key in lifecycle_fields.get(item.object_type, ()):
        if payload.get(key) is not None:
            return (
                f"{_display_token(item.object_type)} · {_display_token(payload[key])}"[
                    :500
                ]
            )
    return f"{item.object_type}:{str(item.id)[:8]}"


def _display_token(value: Any) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _object_text(item: CanonicalEvidenceObject) -> str:
    return _object_label(item)


def _node_response(node: EvidenceGraphProjectionNode) -> dict[str, Any]:
    return {
        "id": node.object_id,
        "object_type": node.object_type,
        "project": node.project,
        "access_class": node.access_class,
        "content_digest": node.content_digest,
        "label": node.label,
        "replay_path": _evidence_replay_path(node.object_id),
    }


def _evidence_replay_path(object_id: UUID) -> str:
    return f"/v1/research/evidence/objects/{object_id}"


def _edge_response(edge: EvidenceGraphProjectionEdge) -> dict[str, Any]:
    return {
        "id": edge.edge_id,
        "source": edge.subject_id,
        "target": edge.object_id,
        "predicate": edge.predicate,
        "valid_from": edge.valid_from,
        "valid_until": edge.valid_until,
        "provenance_object_id": edge.provenance_object_id,
        "access_class": edge.access_class,
        "record_digest": edge.record_digest,
    }


def _encode_graph_cursor(offset: int, fingerprint: str) -> str:
    document = {"fingerprint": fingerprint, "offset": offset}
    return base64.urlsafe_b64encode(_canonical(document)).decode("ascii").rstrip("=")


def _decode_graph_cursor(cursor: str | None, fingerprint: str) -> int:
    if cursor is None:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        document = json.loads(base64.urlsafe_b64decode(cursor + padding))
        offset = document["offset"]
        if (
            document.get("fingerprint") != fingerprint
            or not isinstance(offset, int)
            or isinstance(offset, bool)
            or offset < 0
        ):
            raise ValueError
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(
            status_code=422, detail="Graph cursor does not match this query."
        ) from exc
    return offset


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
