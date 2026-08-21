from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import chain
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, insert, not_, or_, select
from sqlalchemy.orm import Session

from app.models.evidence import (
    CanonicalEvidenceEdge,
    CanonicalEvidenceObject,
    CanonicalIdentityAlias,
)
from app.models.retrieval import (
    EvidenceCorpusFreshness,
    EvidenceRetrievalProjection,
    EvidenceRetrievalState,
)
from app.schemas.retrieval import HybridRetrievalRequest
from app.services.evidence import EvidenceAccessContext, get_evidence_object
from app.services.lifecycle import is_active_expression

PROJECTION_NAME = "canonical-scientific"
PROJECTION_VERSION = "hybrid-retrieval-v1.1.0"
VECTOR_DIMENSIONS = 64
RRF_K = 60
MINIMUM_EVIDENCE_CONFIDENCE = 0.18
CALIBRATION_VERSION = "evidence-confidence-v1"
_ACCESS_LEVEL = {"public": 0, "internal": 1, "restricted": 2, "protected": 3}
_TERMS = re.compile(r"[a-z0-9][a-z0-9_-]*")
_STOP_TERMS = {
    "a",
    "about",
    "after",
    "and",
    "are",
    "be",
    "do",
    "does",
    "evidence",
    "for",
    "from",
    "has",
    "have",
    "in",
    "indicates",
    "is",
    "of",
    "on",
    "or",
    "say",
    "that",
    "the",
    "to",
    "what",
    "when",
    "whether",
    "which",
    "with",
}
_CONCEPTS = {
    "momentum": "concept-trend",
    "trend": "concept-trend",
    "trend-following": "concept-trend",
    "cost": "concept-cost",
    "costs": "concept-cost",
    "fee": "concept-cost",
    "fees": "concept-cost",
    "drawdown": "concept-risk",
    "risk": "concept-risk",
    "volatility": "concept-risk",
}
_PROJECTION_BATCH_SIZE = 1_000
_CALIBRATION_CANDIDATES_PER_CHANNEL = 500
_DATABASE_CANDIDATE_LIMIT = 500
_PRECISE_CANDIDATE_LIMIT = 100
_GRAPH_EXPANSION_LIMIT = 100
_MAX_QUERY_TERMS = 24
_SEARCH_CAPACITY = threading.BoundedSemaphore(8)


def _digest_rows(rows: Iterable[tuple[str, ...]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        encoded = _canonical(list(row))
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def corpus_digest(db: Session) -> str:
    return freshness_snapshot(db)[0]


def corpus_epoch(db: Session) -> int:
    return freshness_snapshot(db)[1]


def freshness_snapshot(db: Session) -> tuple[str, int]:
    row = db.execute(
        select(
            EvidenceCorpusFreshness.corpus_digest,
            EvidenceCorpusFreshness.epoch,
        ).where(EvidenceCorpusFreshness.corpus_name == PROJECTION_NAME)
    ).one_or_none()
    if row is not None and isinstance(row.epoch, int):
        return row.corpus_digest, row.epoch
    return _legacy_corpus_digest(db), 0


def _legacy_corpus_digest(db: Session) -> str:
    object_rows = db.execute(
        select(
            CanonicalEvidenceObject.id,
            CanonicalEvidenceObject.content_digest,
            CanonicalEvidenceObject.object_schema_version,
            CanonicalEvidenceObject.project,
            CanonicalEvidenceObject.access_class,
        )
        .where(CanonicalEvidenceObject.object_type == "scientific_object")
        .where(is_active_expression())
        .order_by(CanonicalEvidenceObject.id)
    ).yield_per(_PROJECTION_BATCH_SIZE)
    scientific_ids = select(CanonicalEvidenceObject.id).where(
        CanonicalEvidenceObject.object_type == "scientific_object",
        is_active_expression(),
    )
    non_scientific_ids = select(CanonicalEvidenceObject.id).where(
        CanonicalEvidenceObject.object_type != "scientific_object"
    )
    edge_rows = db.execute(
        select(
            CanonicalEvidenceEdge.subject_id,
            CanonicalEvidenceEdge.predicate,
            CanonicalEvidenceEdge.object_id,
        )
        .where(
            not_(
                and_(
                    CanonicalEvidenceEdge.subject_id.in_(non_scientific_ids),
                    CanonicalEvidenceEdge.object_id.in_(non_scientific_ids),
                )
            )
        )
        .order_by(
            CanonicalEvidenceEdge.subject_id,
            CanonicalEvidenceEdge.predicate,
            CanonicalEvidenceEdge.object_id,
        )
    ).yield_per(_PROJECTION_BATCH_SIZE)
    alias_rows = db.execute(
        select(
            CanonicalIdentityAlias.canonical_object_id,
            CanonicalIdentityAlias.namespace,
            CanonicalIdentityAlias.native_object_type,
            CanonicalIdentityAlias.alias_value,
        )
        .where(CanonicalIdentityAlias.canonical_object_id.in_(scientific_ids))
        .order_by(
            CanonicalIdentityAlias.canonical_object_id,
            CanonicalIdentityAlias.namespace,
            CanonicalIdentityAlias.native_object_type,
            CanonicalIdentityAlias.alias_value,
        )
    ).yield_per(_PROJECTION_BATCH_SIZE)
    return _digest_rows(
        chain(
            [("version", PROJECTION_VERSION)],
            (
                (
                    "object",
                    str(row.id),
                    row.content_digest,
                    row.object_schema_version,
                    row.project,
                    row.access_class,
                )
                for row in object_rows
            ),
            (
                ("edge", str(row.subject_id), row.predicate, str(row.object_id))
                for row in edge_rows
            ),
            (
                (
                    "alias",
                    str(row.canonical_object_id),
                    row.namespace,
                    row.native_object_type,
                    row.alias_value,
                )
                for row in alias_rows
            ),
        )
    )


def build_projections(db: Session) -> EvidenceRetrievalState:
    digest, source_epoch = freshness_snapshot(db)
    now = datetime.now(UTC)
    db.execute(delete(EvidenceRetrievalProjection))
    db.execute(delete(EvidenceRetrievalState))
    projected_count = 0
    last_id: UUID | None = None
    while True:
        statement = (
            select(
                CanonicalEvidenceObject.id,
                CanonicalEvidenceObject.project,
                CanonicalEvidenceObject.access_class,
                CanonicalEvidenceObject.object_schema_version,
                CanonicalEvidenceObject.content_digest,
                CanonicalEvidenceObject.payload,
            )
            .where(CanonicalEvidenceObject.object_type == "scientific_object")
            .where(is_active_expression())
            .order_by(CanonicalEvidenceObject.id)
            .limit(_PROJECTION_BATCH_SIZE)
        )
        if last_id is not None:
            statement = statement.where(CanonicalEvidenceObject.id > last_id)
        objects = db.execute(statement).all()
        if not objects:
            break
        first_id, last_id = objects[0].id, objects[-1].id
        ids = {row.id for row in objects}
        neighbors: dict[UUID, set[UUID]] = {item: set() for item in ids}
        edge_rows = db.execute(
            select(
                CanonicalEvidenceEdge.subject_id, CanonicalEvidenceEdge.object_id
            ).where(
                or_(
                    CanonicalEvidenceEdge.subject_id.between(first_id, last_id),
                    CanonicalEvidenceEdge.object_id.between(first_id, last_id),
                )
            )
        )
        for subject_id, object_id in edge_rows:
            if subject_id in neighbors:
                neighbors[subject_id].add(object_id)
            if object_id in neighbors:
                neighbors[object_id].add(subject_id)
        aliases_by_id: dict[UUID, list[str]] = {item: [] for item in ids}
        alias_rows = db.execute(
            select(
                CanonicalIdentityAlias.canonical_object_id,
                CanonicalIdentityAlias.namespace,
                CanonicalIdentityAlias.native_object_type,
                CanonicalIdentityAlias.alias_value,
            ).where(
                CanonicalIdentityAlias.canonical_object_id.between(first_id, last_id)
            )
        )
        for object_id, namespace, object_type, value in alias_rows:
            if object_id in aliases_by_id:
                aliases_by_id[object_id].extend(
                    (value, f"{namespace}:{object_type}:{value}")
                )
        mappings = []
        for record in objects:
            text = str(record.payload.get("content_text") or "").strip()
            if not text:
                continue
            terms = term_frequencies(text)
            mappings.append(
                {
                    "object_id": record.id,
                    "project": record.project,
                    "access_class": record.access_class,
                    "object_schema_version": record.object_schema_version,
                    "scientific_type": record.payload["scientific_type"],
                    "content_digest": record.content_digest,
                    "content_text": text,
                    "aliases": sorted(set(aliases_by_id[record.id])),
                    "lexical_terms": terms,
                    "vector": hashed_vector(terms),
                    "graph_neighbors": sorted(neighbors[record.id], key=str),
                    "projection_version": PROJECTION_VERSION,
                    "indexed_at": now,
                }
            )
        if mappings:
            db.execute(insert(EvidenceRetrievalProjection), mappings)
            projected_count += len(mappings)
    final_digest, final_epoch = freshness_snapshot(db)
    if final_digest != digest or final_epoch != source_epoch:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Canonical evidence changed during projection rebuild.",
        )
    state = EvidenceRetrievalState(
        projection_name=PROJECTION_NAME,
        projection_version=PROJECTION_VERSION,
        corpus_digest=digest,
        source_epoch=source_epoch,
        object_count=projected_count,
        built_at=now,
    )
    db.add(state)
    db.commit()
    db.refresh(state)
    return state


def projection_status(db: Session) -> tuple[EvidenceRetrievalState, str, bool]:
    state = db.get(EvidenceRetrievalState, PROJECTION_NAME)
    if state is None:
        raise HTTPException(
            status_code=409, detail="Retrieval projection is not built."
        )
    current, current_epoch = freshness_snapshot(db)
    stale = (
        state.corpus_digest != current
        or getattr(state, "source_epoch", 0) != current_epoch
    )
    return state, current, stale


def hybrid_search(
    db: Session,
    request: HybridRetrievalRequest,
    access: EvidenceAccessContext,
) -> dict:
    if not _SEARCH_CAPACITY.acquire(timeout=0.1):
        raise HTTPException(
            status_code=503,
            detail="Retrieval capacity is temporarily exhausted.",
        )
    try:
        return _hybrid_search(db, request, access)
    finally:
        _SEARCH_CAPACITY.release()


def _hybrid_search(
    db: Session,
    request: HybridRetrievalRequest,
    access: EvidenceAccessContext,
) -> dict:
    started = time.perf_counter()
    state, current_digest, stale = projection_status(db)
    freshness_finished = time.perf_counter()
    if stale:
        raise HTTPException(
            status_code=409,
            detail="Retrieval projection is stale and must be rebuilt.",
        )
    if state.projection_version != request.projection_version:
        raise HTTPException(
            status_code=409, detail="Projection version is incompatible."
        )
    projections = _authorized_projections(db, request, access)
    candidates_finished = time.perf_counter()
    channel_scores = score_channels(projections, request.query)
    selected = calibrated_rankings(
        projections,
        channel_scores,
        request.channels,
        request.query,
        request.limit,
    )
    ranking_finished = time.perf_counter()
    by_id = {item.object_id: item for item in projections}
    hits = []
    for object_id, fused_score, confidence, ranks in selected:
        item = by_id[object_id]
        canonical = get_evidence_object(db, object_id, access, audit=False)
        if canonical.content_digest != item.content_digest:
            raise HTTPException(
                status_code=409,
                detail="Retrieval projection no longer matches canonical evidence.",
            )
        scores = {
            channel: round(channel_scores[channel].get(object_id, 0.0), 8)
            for channel in request.channels
            if object_id in channel_scores[channel]
        }
        coordinates = canonical.payload["coordinates"]
        hits.append(
            {
                "object_id": object_id,
                "project": item.project,
                "access_class": item.access_class,
                "object_schema_version": item.object_schema_version,
                "scientific_type": item.scientific_type,
                "text": item.content_text,
                "score": round(fused_score, 8),
                "confidence": round(confidence, 8),
                "channel_scores": scores,
                "channel_ranks": ranks,
                "citation": {
                    "object_id": object_id,
                    "content_digest": item.content_digest,
                    "coordinates": coordinates,
                    "replay_path": f"/v1/research/retrieval/objects/{object_id}/replay",
                },
            }
        )
    source_epoch = getattr(state, "source_epoch", None)
    if source_epoch is not None:
        final_digest, final_epoch = freshness_snapshot(db)
        if final_digest != current_digest or final_epoch != source_epoch:
            raise HTTPException(
                status_code=409,
                detail="Canonical evidence changed during retrieval.",
            )
    completed = time.perf_counter()
    return {
        "query": request.query,
        "projection_version": state.projection_version,
        "corpus_digest": current_digest,
        "fusion": request.fusion,
        "stale": False,
        "confidence": round(hits[0]["confidence"], 8) if hits else 0.0,
        "abstained": not hits,
        "calibration": CALIBRATION_VERSION,
        "timings_ms": {
            "freshness": _milliseconds(started, freshness_finished),
            "candidates": _milliseconds(freshness_finished, candidates_finished),
            "ranking": _milliseconds(candidates_finished, ranking_finished),
            "authorization_and_hydration": _milliseconds(
                ranking_finished, completed
            ),
            "total": _milliseconds(started, completed),
        },
        "candidate_counts": {
            "bounded": len(projections),
            **{
                channel: len(channel_scores[channel])
                for channel in request.channels
            },
        },
        "hits": hits,
    }


def score_channels(
    projections: Iterable[EvidenceRetrievalProjection], query: str
) -> dict[str, dict[UUID, float]]:
    items = list(projections)
    normalized = query.strip().lower()
    query_terms = term_frequencies(query)
    query_vector = hashed_vector(query_terms)
    exact: dict[UUID, float] = {}
    lexical: dict[UUID, float] = {}
    vector: dict[UUID, float] = {}
    for item in items:
        identifiers = {
            str(item.object_id).lower(),
            item.content_digest.lower(),
            *(str(alias).lower() for alias in item.aliases),
        }
        if normalized in identifiers:
            exact[item.object_id] = 1.0
        elif normalized and normalized in item.content_text.lower():
            exact[item.object_id] = 0.75
        lexical_score = cosine_counts(query_terms, item.lexical_terms)
        if lexical_score > 0:
            lexical[item.object_id] = lexical_score
        vector_score = cosine_vectors(query_vector, item.vector)
        if vector_score > 0:
            vector[item.object_id] = vector_score
    seed_ids = {
        object_id
        for scores in (exact, lexical, vector)
        for object_id, _ in _rank(scores)[:5]
    }
    graph: dict[UUID, float] = {}
    seed_neighbors = {
        neighbor
        for item in items
        if item.object_id in seed_ids
        for neighbor in item.graph_neighbors
    }
    for item in items:
        overlap = len(set(item.graph_neighbors) & seed_ids)
        if item.object_id in seed_neighbors:
            overlap += 1
        if overlap:
            graph[item.object_id] = min(1.0, overlap / 3)
    return {"exact": exact, "lexical": lexical, "vector": vector, "graph": graph}


def fuse_rankings(
    scores: dict[str, dict[UUID, float]], channels: list[str], limit: int
) -> list[tuple[UUID, float, dict[str, int]]]:
    fused: dict[UUID, float] = {}
    ranks_by_id: dict[UUID, dict[str, int]] = {}
    for channel in channels:
        for rank, (object_id, _) in enumerate(_rank(scores[channel]), 1):
            fused[object_id] = fused.get(object_id, 0.0) + 1 / (RRF_K + rank)
            ranks_by_id.setdefault(object_id, {})[channel] = rank
    ordered = sorted(fused, key=lambda item: (-fused[item], str(item)))[:limit]
    return [(item, fused[item], ranks_by_id[item]) for item in ordered]


def calibrated_rankings(
    projections: Iterable[EvidenceRetrievalProjection],
    scores: dict[str, dict[UUID, float]],
    channels: list[str],
    query: str,
    limit: int,
) -> list[tuple[UUID, float, float, dict[str, int]]]:
    items = list(projections)
    by_id = {item.object_id: item for item in items}
    fused_scores: dict[UUID, float] = {}
    ranks_by_id: dict[UUID, dict[str, int]] = {}
    for channel in channels:
        for rank, (object_id, _) in enumerate(
            _rank(scores[channel])[:_CALIBRATION_CANDIDATES_PER_CHANNEL], 1
        ):
            fused_scores[object_id] = fused_scores.get(object_id, 0.0) + 1 / (
                RRF_K + rank
            )
            ranks_by_id.setdefault(object_id, {})[channel] = rank
    fused = sorted(
        (
            (object_id, fused_score, ranks_by_id[object_id])
            for object_id, fused_score in fused_scores.items()
        ),
        key=lambda item: (-item[1], str(item[0])),
    )
    query_terms = informative_terms(query)
    anchors = explicit_anchor_terms(query)
    requested_concepts = query_concepts(query_terms)
    calibrated = []
    for object_id, fused_score, ranks in fused:
        item = by_id[object_id]
        item_terms = set(item.lexical_terms)
        identifiers = " ".join(
            (str(item.object_id), item.content_digest, *map(str, item.aliases))
        ).lower()
        searchable = f"{item.content_text.lower()} {identifiers}"
        if anchors and not anchors.issubset(set(_TERMS.findall(searchable))):
            continue
        overlap = query_terms & item_terms
        concept_overlap = requested_concepts & query_concepts(item_terms)
        exact = scores["exact"].get(object_id, 0.0)
        lexical = scores["lexical"].get(object_id, 0.0)
        if exact == 0 and len(overlap) < 2 and not concept_overlap:
            continue
        coverage = len(overlap) / len(query_terms) if query_terms else 0.0
        concept_coverage = (
            len(concept_overlap) / len(requested_concepts)
            if requested_concepts
            else 0.0
        )
        confidence = min(
            1.0,
            (0.55 * coverage)
            + (0.25 * lexical)
            + (0.15 * exact)
            + (0.05 * concept_coverage),
        )
        if exact == 1.0:
            confidence = max(confidence, 0.95)
        if confidence >= MINIMUM_EVIDENCE_CONFIDENCE:
            calibrated.append((object_id, fused_score, confidence, ranks))
    return sorted(
        calibrated,
        key=lambda item: (-item[2], -item[1], str(item[0])),
    )[:limit]


def informative_terms(text: str) -> set[str]:
    return set(term_frequencies(text)) - _STOP_TERMS


def explicit_anchor_terms(text: str) -> set[str]:
    return {
        token
        for token in _TERMS.findall(text.lower())
        if any(character.isdigit() for character in token)
    }


def query_concepts(terms: Iterable[str]) -> set[str]:
    return {_CONCEPTS[term] for term in terms if term in _CONCEPTS}


def term_frequencies(text: str) -> dict[str, int]:
    terms: list[str] = []
    for token in _TERMS.findall(text.lower()):
        terms.append(token)
        if "_" in token or "-" in token:
            terms.extend(item for item in re.split(r"[_-]+", token) if item)
    return dict(Counter(terms))


def hashed_vector(terms: dict[str, int]) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    expanded = Counter(terms)
    for term, frequency in terms.items():
        concept = _CONCEPTS.get(term)
        if concept is not None:
            expanded[concept] += frequency
    for term, frequency in expanded.items():
        digest = hashlib.sha256(term.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign * float(frequency)
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


def cosine_counts(left: dict[str, int], right: dict[str, int]) -> float:
    common = set(left) & set(right)
    numerator = sum(left[item] * right[item] for item in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def cosine_vectors(left: list[float], right: list[float]) -> float:
    similarity = sum(a * b for a, b in zip(left, right, strict=True))
    return max(0.0, similarity)


def _authorized_projections(
    db: Session,
    request: HybridRetrievalRequest,
    access: EvidenceAccessContext,
) -> list[EvidenceRetrievalProjection]:
    statement = _authorized_statement(request, access)
    normalized = request.query.strip().lower()
    exact_conditions = []
    try:
        exact_conditions.append(EvidenceRetrievalProjection.object_id == UUID(normalized))
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-f]{64}", normalized):
        exact_conditions.append(
            EvidenceRetrievalProjection.content_digest == normalized
        )
    exact_conditions.append(EvidenceRetrievalProjection.aliases.contains([normalized]))
    exact = list(
        db.scalars(
            statement.where(or_(*exact_conditions))
            .order_by(EvidenceRetrievalProjection.object_id)
            .limit(100)
        ).all()
    )

    informative = sorted(informative_terms(request.query))[:_MAX_QUERY_TERMS]
    terms = sorted(candidate_terms(request.query))[:_MAX_QUERY_TERMS]
    lexical = []
    if terms:
        document = func.to_tsvector(
            "simple", EvidenceRetrievalProjection.content_text
        )
        if informative:
            precise_query = func.plainto_tsquery(
                "simple", " ".join(informative)
            )
            lexical.extend(
                db.scalars(
                    statement.where(document.op("@@")(precise_query))
                    .order_by(
                        func.ts_rank_cd(document, precise_query).desc(),
                        EvidenceRetrievalProjection.object_id,
                    )
                    .limit(_PRECISE_CANDIDATE_LIMIT)
                ).all()
            )
        candidate_query = func.to_tsquery("simple", " | ".join(terms))
        lexical.extend(
            db.scalars(
                statement.where(document.op("@@")(candidate_query))
                .limit(_DATABASE_CANDIDATE_LIMIT)
            ).all()
        )

    candidates = {item.object_id: item for item in (*exact, *lexical)}
    if candidates and "graph" in request.channels:
        initial_scores = score_channels(candidates.values(), request.query)
        seed_ids = {
            object_id
            for scores in initial_scores.values()
            for object_id, _ in _rank(scores)[:5]
        }
        neighbor_ids = sorted(
            {
                neighbor
                for item in candidates.values()
                if item.object_id in seed_ids
                for neighbor in item.graph_neighbors
            },
            key=str,
        )[:_GRAPH_EXPANSION_LIMIT]
        if neighbor_ids:
            neighbors = db.scalars(
                statement.where(
                    EvidenceRetrievalProjection.object_id.in_(neighbor_ids)
                ).order_by(EvidenceRetrievalProjection.object_id)
            ).all()
            candidates.update((item.object_id, item) for item in neighbors)
    return sorted(candidates.values(), key=lambda item: str(item.object_id))


def _authorized_statement(
    request: HybridRetrievalRequest,
    access: EvidenceAccessContext,
):
    statement = select(EvidenceRetrievalProjection).where(
        EvidenceRetrievalProjection.object_schema_version.in_(
            request.compatible_schema_versions
        ),
        EvidenceRetrievalProjection.access_class.in_(
            [
                name
                for name, level in _ACCESS_LEVEL.items()
                if level <= _ACCESS_LEVEL[access.max_access_class]
            ]
        ),
    )
    if "*" not in access.projects:
        statement = statement.where(
            EvidenceRetrievalProjection.project.in_(access.projects)
        )
    if request.project is not None:
        if "*" not in access.projects and request.project not in access.projects:
            raise HTTPException(
                status_code=403, detail="Evidence project access denied."
            )
        statement = statement.where(
            EvidenceRetrievalProjection.project == request.project
        )
    if request.scientific_types:
        statement = statement.where(
            EvidenceRetrievalProjection.scientific_type.in_(request.scientific_types)
        )
    return statement


def candidate_terms(query: str) -> set[str]:
    terms = informative_terms(query)
    concepts = query_concepts(terms)
    expanded = set(terms)
    expanded.update(
        term for term, concept in _CONCEPTS.items() if concept in concepts
    )
    return expanded


def _rank(scores: dict[UUID, float]) -> list[tuple[UUID, float]]:
    return sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _milliseconds(start: float, end: float) -> float:
    return round((end - start) * 1_000, 3)
