from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corpus_sync import CorpusSyncRun
from app.models.curriculum import ResearchBrainEvaluation, ResearchDomainCurriculum
from app.models.evidence import CanonicalEvidenceObject
from app.schemas.curriculum import BrainEvaluationCreate, DomainCurriculumCreate
from app.schemas.retrieval import HybridRetrievalRequest
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.graph import digest_document, graph_projection_status
from app.services.retrieval import hybrid_search, projection_status

SearchFunction = Callable[[Session, HybridRetrievalRequest, Any], dict[str, Any]]


def register_curriculum(
    db: Session, payload: DomainCurriculumCreate
) -> ResearchDomainCurriculum:
    retrieval_state, current_corpus, retrieval_stale = projection_status(db)
    graph_state, graph_stale = graph_projection_status(db)
    if (
        retrieval_stale
        or graph_stale
        or retrieval_state.corpus_digest != current_corpus
    ):
        raise HTTPException(status_code=409, detail="Corpus projections are stale.")

    object_ids = {
        object_id
        for topic in payload.topics
        for object_id in (
            topic.evidence_object_ids
            + topic.source_object_ids
            + topic.opposing_evidence_object_ids
        )
    }
    objects = {
        item.id: item
        for item in db.scalars(
            select(CanonicalEvidenceObject).where(
                CanonicalEvidenceObject.id.in_(object_ids)
            )
        )
    }
    if set(objects) != object_ids:
        raise HTTPException(
            status_code=422, detail="Curriculum references unknown evidence."
        )
    allowed_authority = set(payload.source_quality.allowed_authority_classes)
    for item in objects.values():
        if item.project != payload.project:
            raise HTTPException(
                status_code=422,
                detail="Curriculum evidence must belong to its declared project.",
            )
        if item.authority_class not in allowed_authority:
            raise HTTPException(
                status_code=422,
                detail="Curriculum evidence does not meet its authority rubric.",
            )
    for topic in payload.topics:
        if any(
            objects[object_id].object_type != "source"
            for object_id in topic.source_object_ids
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Topic {topic.key} source anchors must be source objects.",
            )
        minimum = max(
            topic.minimum_sources,
            payload.source_quality.minimum_distinct_sources_per_topic,
        )
        if len(topic.source_object_ids) < minimum:
            raise HTTPException(
                status_code=422,
                detail=f"Topic {topic.key} lacks distinct source coverage.",
            )
        if (
            payload.source_quality.require_opposing_evidence
            and not topic.opposing_evidence_object_ids
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Topic {topic.key} lacks opposing evidence.",
            )

    specification = payload.model_dump(
        mode="json", exclude={"domain_key", "version", "title", "project", "created_by"}
    )
    document = {
        "domain_key": payload.domain_key,
        "version": payload.version,
        "title": payload.title,
        "project": payload.project,
        "specification": specification,
        "corpus_digest": current_corpus,
        "graph_manifest_digest": graph_state.manifest_digest,
        "status": "draft",
        "created_by": payload.created_by,
    }
    digest = digest_document(document)
    existing = db.scalar(
        select(ResearchDomainCurriculum).where(
            ResearchDomainCurriculum.domain_key == payload.domain_key,
            ResearchDomainCurriculum.version == payload.version,
        )
    )
    if existing is not None:
        if existing.record_digest == digest:
            return existing
        raise HTTPException(status_code=409, detail="Curriculum version is immutable.")
    record = ResearchDomainCurriculum(**document, record_digest=digest)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def evaluate_curriculum(
    db: Session,
    payload: BrainEvaluationCreate,
    *,
    search: SearchFunction = hybrid_search,
) -> ResearchBrainEvaluation:
    curriculum = db.get(ResearchDomainCurriculum, payload.curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    retrieval_state, current_corpus, retrieval_stale = projection_status(db)
    graph_state, graph_stale = graph_projection_status(db)
    if retrieval_stale or graph_stale:
        raise HTTPException(status_code=409, detail="Corpus projections are stale.")
    if (
        curriculum.corpus_digest != current_corpus
        or curriculum.graph_manifest_digest != graph_state.manifest_digest
        or retrieval_state.corpus_digest != current_corpus
    ):
        raise HTTPException(
            status_code=409, detail="Curriculum is stale for the current corpus."
        )

    case_results = []
    recalls: list[float] = []
    opposition_recalls: list[float] = []
    citation_checks: list[float] = []
    abstention_checks: list[float] = []
    leakage_checks: list[float] = []
    for case in payload.cases:
        result = search(
            db,
            HybridRetrievalRequest(
                query=case.query,
                project=curriculum.project,
                limit=50,
            ),
            ORCHESTRATOR_ACCESS,
        )
        returned = {item["object_id"] for item in result["hits"]}
        expected = set(case.expected_object_ids)
        opposing = set(case.opposing_object_ids)
        forbidden = set(case.forbidden_object_ids)
        recall = len(returned & expected) / len(expected) if expected else 1.0
        opposition = len(returned & opposing) / len(opposing) if opposing else 1.0
        citations_valid = all(
            item.get("citation", {}).get("object_id") == item.get("object_id")
            and bool(item.get("citation", {}).get("replay_path"))
            and bool(item.get("citation", {}).get("content_digest"))
            for item in result["hits"]
        )
        abstained = bool(result.get("abstained", not result["hits"]))
        leakage = len(returned & forbidden) / len(returned) if returned else 0.0
        recalls.append(recall)
        opposition_recalls.append(opposition)
        citation_checks.append(float(citations_valid))
        abstention_checks.append(float(abstained == case.should_abstain))
        leakage_checks.append(leakage)
        case_results.append(
            {
                "case_key": case.case_key,
                "query_digest": digest_document({"query": case.query}),
                "retrieval_corpus_digest": result["corpus_digest"],
                "returned_object_ids": sorted(map(str, returned)),
                "retrieval_recall": recall,
                "opposition_recall": opposition,
                "citation_fidelity": float(citations_valid),
                "abstention_correct": abstained == case.should_abstain,
                "cross_domain_leakage": leakage,
            }
        )

    topic_coverage = _topic_coverage(curriculum)
    metrics = {
        "retrieval_recall": _mean(recalls),
        "citation_fidelity": _mean(citation_checks),
        "opposition_recall": _mean(opposition_recalls),
        "abstention_accuracy": _mean(abstention_checks),
        "cross_domain_leakage": _mean(leakage_checks),
        "topic_coverage": topic_coverage,
        "case_count": len(case_results),
    }
    thresholds = payload.thresholds.model_dump(mode="json")
    passed = (
        metrics["retrieval_recall"] >= thresholds["minimum_retrieval_recall"]
        and metrics["citation_fidelity"] >= thresholds["minimum_citation_fidelity"]
        and metrics["opposition_recall"] >= thresholds["minimum_opposition_recall"]
        and metrics["abstention_accuracy"] >= thresholds["minimum_abstention_accuracy"]
        and metrics["cross_domain_leakage"]
        <= thresholds["maximum_cross_domain_leakage"]
        and metrics["topic_coverage"] >= thresholds["minimum_topic_coverage"]
    )
    evaluation_set_digest = digest_document(
        [case.model_dump(mode="json") for case in payload.cases]
    )
    document = {
        "curriculum_id": str(curriculum.id),
        "evaluation_version": payload.evaluation_version,
        "corpus_digest": current_corpus,
        "graph_manifest_digest": graph_state.manifest_digest,
        "evaluation_set_digest": evaluation_set_digest,
        "thresholds": thresholds,
        "metrics": metrics,
        "cases": case_results,
        "passed": passed,
        "status": "qualified" if passed else "gaps_detected",
        "review_due_days": curriculum.specification["review_cadence_days"],
        "evaluated_by": payload.evaluated_by,
    }
    digest = digest_document(document)
    existing = db.scalar(
        select(ResearchBrainEvaluation).where(
            ResearchBrainEvaluation.curriculum_id == curriculum.id,
            ResearchBrainEvaluation.evaluation_version == payload.evaluation_version,
        )
    )
    if existing is not None:
        if existing.record_digest == digest:
            return existing
        raise HTTPException(status_code=409, detail="Evaluation version is immutable.")
    record = ResearchBrainEvaluation(
        curriculum_id=curriculum.id,
        evaluation_version=payload.evaluation_version,
        corpus_digest=current_corpus,
        graph_manifest_digest=graph_state.manifest_digest,
        evaluation_set_digest=evaluation_set_digest,
        thresholds=thresholds,
        metrics=metrics,
        cases=case_results,
        passed=passed,
        status=document["status"],
        review_due_days=document["review_due_days"],
        evaluated_by=payload.evaluated_by,
        record_digest=digest,
        evaluated_at=datetime.now(UTC),
    )
    db.add(record)
    curriculum.status = "qualified" if passed else "draft"
    db.commit()
    db.refresh(record)
    return record


def domain_readiness(
    db: Session, curriculum: ResearchDomainCurriculum
) -> dict[str, Any]:
    latest = db.scalar(
        select(ResearchBrainEvaluation)
        .where(ResearchBrainEvaluation.curriculum_id == curriculum.id)
        .order_by(ResearchBrainEvaluation.evaluated_at.desc())
    )
    _, current_corpus, retrieval_stale = projection_status(db)
    graph_state, graph_stale = graph_projection_status(db)
    coverage = _topic_coverage(curriculum)
    topics = curriculum.specification["topics"]
    latest_sync = db.scalar(
        select(CorpusSyncRun)
        .where(CorpusSyncRun.project == curriculum.project)
        .order_by(CorpusSyncRun.created_at.desc())
    )
    quarantined = int((latest_sync.counts if latest_sync else {}).get("quarantined", 0))
    reasons = []
    if curriculum.corpus_digest != current_corpus:
        reasons.append("curriculum_corpus_stale")
    if curriculum.graph_manifest_digest != graph_state.manifest_digest:
        reasons.append("curriculum_graph_stale")
    if retrieval_stale or graph_stale:
        reasons.append("projection_stale")
    if latest is None or not latest.passed:
        reasons.append("evaluation_not_passing")
    if latest is not None and latest.corpus_digest != current_corpus:
        reasons.append("evaluation_corpus_stale")
    maximum = curriculum.specification["source_quality"]["maximum_quarantined_fraction"]
    inventory = sum((latest_sync.counts if latest_sync else {}).values())
    if inventory and quarantined / inventory > maximum:
        reasons.append("quarantine_ceiling_exceeded")
    return {
        "domain_key": curriculum.domain_key,
        "curriculum_id": curriculum.id,
        "curriculum_version": curriculum.version,
        "curriculum_status": curriculum.status,
        "corpus_digest": current_corpus,
        "graph_manifest_digest": graph_state.manifest_digest,
        "topic_count": len(topics),
        "covered_topic_count": round(coverage * len(topics)),
        "topic_coverage": coverage,
        "quarantined_items": quarantined,
        "evaluation": latest,
        "ready": not reasons,
        "reasons": reasons,
    }


def curriculum_response(record: ResearchDomainCurriculum) -> dict[str, Any]:
    return {
        "id": record.id,
        "domain_key": record.domain_key,
        "version": record.version,
        "title": record.title,
        "project": record.project,
        **record.specification,
        "corpus_digest": record.corpus_digest,
        "graph_manifest_digest": record.graph_manifest_digest,
        "status": record.status,
        "record_digest": record.record_digest,
        "created_by": record.created_by,
        "created_at": record.created_at,
    }


def _topic_coverage(curriculum: ResearchDomainCurriculum) -> float:
    topics = curriculum.specification["topics"]
    rubric = curriculum.specification["source_quality"]
    covered = sum(
        len(topic["source_object_ids"]) >= topic["minimum_sources"]
        and (
            not rubric["require_opposing_evidence"]
            or bool(topic["opposing_evidence_object_ids"])
        )
        for topic in topics
    )
    return covered / len(topics)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0
