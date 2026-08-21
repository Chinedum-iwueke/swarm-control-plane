from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import deque
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from itertools import chain
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, insert, or_, select
from sqlalchemy.orm import Session

from app.models.evidence import CanonicalEvidenceEdge, CanonicalEvidenceObject
from app.models.graph import (
    CognitiveToolReceipt,
    EvidenceGraphProjectionEdge,
    EvidenceGraphProjectionNode,
    EvidenceGraphProjectionState,
)
from app.schemas.graph import (
    CanonicalEdgeCreate,
    CognitiveToolRequest,
    ContextPackRequest,
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
    "uses_method": {("run", "method")},
    "uses_dataset": {("run", "dataset"), ("method", "dataset")},
    "produced_result": {("run", "result")},
    "reviews": {("review", "claim"), ("review", "run"), ("review", "result")},
    "decides_on": {
        ("decision", "result"),
        ("decision", "claim"),
        ("decision", "belief"),
    },
    "belongs_to_trial_family": {("run", "claim"), ("result", "claim")},
    "depends_on": {
        ("claim", "assumption"),
        ("method", "assumption"),
        ("belief", "belief"),
    },
    "cites": {("claim", "scientific_object"), ("method", "scientific_object")},
}
_PROJECTION_BATCH_SIZE = 2_000


def _stream_digest(rows) -> str:
    digest = hashlib.sha256()
    for row in rows:
        encoded = _canonical(row)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def digest_document(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def register_edge(
    db: Session,
    payload: CanonicalEdgeCreate,
    access: EvidenceAccessContext,
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
    db.commit()
    db.refresh(record)
    return record


def graph_corpus_digest(db: Session) -> str:
    active_ids = select(CanonicalEvidenceObject.id).where(is_active_expression())
    objects = db.execute(
        select(
            CanonicalEvidenceObject.id,
            CanonicalEvidenceObject.content_digest,
            CanonicalEvidenceObject.object_type,
            CanonicalEvidenceObject.project,
            CanonicalEvidenceObject.access_class,
        ).where(is_active_expression()).order_by(CanonicalEvidenceObject.id)
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
        ).where(
            CanonicalEvidenceEdge.subject_id.in_(active_ids),
            CanonicalEvidenceEdge.object_id.in_(active_ids),
        ).order_by(
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
        )
    )


def build_graph_projection(db: Session) -> EvidenceGraphProjectionState:
    source_epoch = corpus_epoch(db)
    corpus = graph_corpus_digest(db)
    now = datetime.now(UTC)
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
        built_at=now,
    )
    db.add(state)
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
    initial = _authorized_node_subset(db, requested, access, request.project)
    if set(initial) != requested:
        raise HTTPException(
            status_code=404, detail="Graph root or target is unavailable."
        )
    by_id = dict(initial)
    edges: list[EvidenceGraphProjectionEdge] = []
    frontier = set(request.root_ids)
    for _depth in range(request.max_depth):
        if not frontier or len(by_id) >= request.max_nodes:
            break
        candidates = _frontier_edges(db, frontier, access, request)
        candidate_ids = {
            node_id
            for edge in candidates
            for node_id in (
                edge.subject_id,
                edge.object_id,
                edge.provenance_object_id,
            )
        }
        authorized = _authorized_node_subset(db, candidate_ids, access, request.project)
        authorized_ids = set(authorized)
        accepted = [
            edge
            for edge in candidates
            if {
                edge.subject_id,
                edge.object_id,
                edge.provenance_object_id,
            }
            <= authorized_ids
        ]
        previous = set(by_id)
        for node_id in sorted(authorized, key=str):
            if len(by_id) >= request.max_nodes and node_id not in by_id:
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
    adjacency = _adjacency(edges, request.direction)
    visited, paths = _traverse(request, adjacency)
    selected_ids = set(list(visited)[: request.max_nodes])
    selected_edges = [
        edge
        for edge in edges
        if edge.subject_id in selected_ids and edge.object_id in selected_ids
    ]
    document = {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "request": request.model_dump(mode="json"),
        "node_ids": sorted(map(str, selected_ids)),
        "edge_digests": sorted(edge.record_digest for edge in selected_edges),
    }
    return {
        "projection_version": state.projection_version,
        "corpus_digest": state.corpus_digest,
        "query_digest": digest_document(document),
        "nodes": [
            _node_response(by_id[item]) for item in sorted(selected_ids, key=str)
        ],
        "edges": [_edge_response(item) for item in selected_edges],
        "paths": paths,
        "truncated": len(visited) > request.max_nodes,
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
    }


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
        "proposition",
        "name",
        "statement",
        "decision",
        "content_text",
    ):
        if payload.get(key):
            return str(payload[key])[:500]
    return f"{item.object_type}:{str(item.id)[:8]}"


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
        "record_digest": edge.record_digest,
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
