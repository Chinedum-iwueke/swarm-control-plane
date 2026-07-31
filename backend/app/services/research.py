import hashlib
import json
import re
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ResearchBrief,
    ResearchChunk,
    ResearchDecision,
    ResearchDocument,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchRetrievalEvaluation,
    ResearchReview,
    ResearchSource,
    ResearchTrial,
)
from app.schemas.research import (
    ResearchBriefCreate,
    ResearchChunkCreate,
    ResearchDecisionCreate,
    ResearchDocumentCreate,
    ResearchExperimentCreate,
    ResearchHypothesisCreate,
    ResearchResultCreate,
    ResearchReviewCreate,
    ResearchSourceCreate,
    ResearchTrialCreate,
    RetrievalEvaluationCreate,
)

_TERMS = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")


def record_digest(document: Any) -> str:
    if hasattr(document, "model_dump"):
        document = document.model_dump(mode="json")
    canonical = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _require_digest(actual: str, supplied: str, label: str) -> None:
    if actual != supplied:
        raise HTTPException(status_code=422, detail=f"{label} digest mismatch.")


def _commit(db: Session, record: Any, conflict: str) -> Any:
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from exc
    db.refresh(record)
    return record


def register_source(db: Session, payload: ResearchSourceCreate) -> ResearchSource:
    _require_digest(
        record_digest(payload.specification), payload.record_digest, "Source"
    )
    return _commit(
        db,
        ResearchSource(
            source_key=payload.source_key,
            specification=payload.specification.model_dump(mode="json"),
            record_digest=payload.record_digest,
            registered_by=payload.registered_by,
        ),
        "Source key or digest already exists.",
    )


def register_hypothesis(
    db: Session, payload: ResearchHypothesisCreate
) -> ResearchHypothesis:
    _require_digest(
        record_digest(payload.specification), payload.record_digest, "Hypothesis"
    )
    return _commit(
        db,
        ResearchHypothesis(
            hypothesis_key=payload.hypothesis_key,
            trial_family=payload.trial_family,
            specification=payload.specification.model_dump(mode="json"),
            record_digest=payload.record_digest,
            registered_by=payload.registered_by,
        ),
        "Hypothesis key or digest already exists.",
    )


def register_experiment(
    db: Session, payload: ResearchExperimentCreate
) -> ResearchExperiment:
    hypothesis = db.get(ResearchHypothesis, payload.hypothesis_id)
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found.")
    if db.get(ResearchSource, payload.source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    hypothesis_approved = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "hypothesis",
            ResearchReview.subject_id == hypothesis.id,
            ResearchReview.subject_digest == hypothesis.record_digest,
            ResearchReview.review_kind == "approval",
            ResearchReview.verdict == "approved",
        )
    )
    if hypothesis_approved is None:
        raise HTTPException(status_code=409, detail="Exact hypothesis is not approved.")
    _require_digest(
        record_digest(payload.manifest), payload.manifest_digest, "Experiment manifest"
    )
    return _commit(
        db,
        ResearchExperiment(
            experiment_key=payload.experiment_key,
            hypothesis_id=payload.hypothesis_id,
            source_id=payload.source_id,
            manifest=payload.manifest.model_dump(mode="json"),
            manifest_digest=payload.manifest_digest,
            registered_by=payload.registered_by,
        ),
        "Experiment key or manifest digest already exists.",
    )


def add_review(
    db: Session,
    subject_type: str,
    subject_id: UUID,
    payload: ResearchReviewCreate,
) -> ResearchReview:
    model, digest_field = {
        "hypothesis": (ResearchHypothesis, "record_digest"),
        "experiment": (ResearchExperiment, "manifest_digest"),
        "result": (ResearchResult, "record_digest"),
    }[subject_type]
    subject = db.get(model, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Review subject not found.")
    expected = getattr(subject, digest_field)
    _require_digest(expected, payload.subject_digest, "Review subject")
    if (
        payload.review_kind == "approval"
        and subject_type in {"hypothesis", "experiment"}
        and subject.registered_by == payload.reviewer
    ):
        raise HTTPException(
            status_code=422, detail="A record author cannot approve their own record."
        )
    if subject_type == "result":
        trial = db.get(ResearchTrial, subject.trial_id)
        if trial is not None and trial.executed_by == payload.reviewer:
            raise HTTPException(
                status_code=422,
                detail="Result reviewer must be independent from the executor.",
            )
    document = {
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        **payload.model_dump(mode="json"),
    }
    return _commit(
        db,
        ResearchReview(
            subject_type=subject_type,
            subject_id=subject_id,
            subject_digest=payload.subject_digest,
            review_kind=payload.review_kind,
            verdict=payload.verdict,
            review=payload.review,
            record_digest=record_digest(document),
            reviewer=payload.reviewer,
        ),
        "This reviewer already recorded that review for this subject.",
    )


def register_trial(
    db: Session, experiment_id: UUID, payload: ResearchTrialCreate
) -> ResearchTrial:
    experiment = db.get(ResearchExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    _require_digest(experiment.manifest_digest, payload.experiment_digest, "Experiment")
    approved = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "experiment",
            ResearchReview.subject_id == experiment.id,
            ResearchReview.subject_digest == experiment.manifest_digest,
            ResearchReview.review_kind == "approval",
            ResearchReview.verdict == "approved",
        )
    )
    if approved is None:
        raise HTTPException(
            status_code=409, detail="Exact experiment manifest is not approved."
        )
    hypothesis = db.get(ResearchHypothesis, experiment.hypothesis_id)
    assert hypothesis is not None
    db.scalars(
        select(ResearchHypothesis)
        .where(ResearchHypothesis.trial_family == hypothesis.trial_family)
        .with_for_update()
    ).all()
    family_count = (
        db.scalar(
            select(func.count(ResearchTrial.id)).where(
                ResearchTrial.trial_family == hypothesis.trial_family
            )
        )
        or 0
    )
    maximum = int(hypothesis.specification["maximum_trials"])
    if family_count >= maximum:
        raise HTTPException(status_code=409, detail="Trial-family budget is exhausted.")
    trial_number = family_count + 1
    document = {
        "experiment_digest": payload.experiment_digest,
        "trial_number": trial_number,
        "plan": payload.plan.model_dump(mode="json"),
        "executed_by": payload.executed_by,
    }
    _require_digest(record_digest(document), payload.record_digest, "Trial")
    return _commit(
        db,
        ResearchTrial(
            experiment_id=experiment.id,
            trial_family=hypothesis.trial_family,
            run_id=payload.plan.run_id,
            trial_number=trial_number,
            plan=payload.plan.model_dump(mode="json"),
            record_digest=payload.record_digest,
            executed_by=payload.executed_by,
        ),
        "Trial run, digest, or family sequence already exists.",
    )


def register_result(
    db: Session, trial_id: UUID, payload: ResearchResultCreate
) -> ResearchResult:
    trial = db.get(ResearchTrial, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found.")
    _require_digest(trial.record_digest, payload.trial_digest, "Trial")
    document = {
        "trial_digest": payload.trial_digest,
        "outcome": payload.outcome,
        "result": payload.result.model_dump(mode="json"),
        "recorded_by": payload.recorded_by,
    }
    _require_digest(record_digest(document), payload.record_digest, "Result")
    return _commit(
        db,
        ResearchResult(
            trial_id=trial.id,
            outcome=payload.outcome,
            result=payload.result.model_dump(mode="json"),
            record_digest=payload.record_digest,
            recorded_by=payload.recorded_by,
        ),
        "A result already exists for this trial or digest.",
    )


def register_decision(
    db: Session, result_id: UUID, payload: ResearchDecisionCreate
) -> ResearchDecision:
    result = db.get(ResearchResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    _require_digest(result.record_digest, payload.result_digest, "Result")
    independent_review = db.scalar(
        select(ResearchReview.id).where(
            ResearchReview.subject_type == "result",
            ResearchReview.subject_id == result.id,
            ResearchReview.subject_digest == result.record_digest,
            ResearchReview.review_kind.in_(
                ("independent_review", "adversarial_review")
            ),
        )
    )
    if independent_review is None:
        raise HTTPException(
            status_code=409, detail="Independent result review required."
        )
    document = payload.model_dump(mode="json") | {"result_id": str(result_id)}
    return _commit(
        db,
        ResearchDecision(
            result_id=result.id,
            decision=payload.decision,
            rationale=payload.rationale,
            result_digest=payload.result_digest,
            record_digest=record_digest(document),
            decided_by=payload.decided_by,
        ),
        "Decision digest already exists.",
    )


def corpus_digest(db: Session) -> str:
    digests = db.scalars(
        select(ResearchDocument.content_digest).order_by(ResearchDocument.document_key)
    ).all()
    return hashlib.sha256("\n".join(digests).encode()).hexdigest()


def register_document(db: Session, payload: ResearchDocumentCreate) -> ResearchDocument:
    return _commit(
        db,
        ResearchDocument(
            document_key=payload.document_key,
            title=payload.title,
            document_type=payload.document_type,
            evidence_type=payload.evidence_type,
            version=payload.version,
            source_uri=payload.source_uri,
            content_digest=payload.content_digest,
            metadata_=payload.metadata,
            ingested_by=payload.ingested_by,
        ),
        "Document key or content digest already exists.",
    )


def register_chunk(
    db: Session, document_id: UUID, payload: ResearchChunkCreate
) -> ResearchChunk:
    if db.get(ResearchDocument, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    actual = hashlib.sha256(payload.text.encode()).hexdigest()
    _require_digest(actual, payload.text_digest, "Passage")
    return _commit(
        db,
        ResearchChunk(
            document_id=document_id,
            ordinal=payload.ordinal,
            section=payload.section,
            page=payload.page,
            line_start=payload.line_start,
            line_end=payload.line_end,
            text=payload.text,
            text_digest=payload.text_digest,
            metadata_=payload.metadata,
        ),
        "Passage ordinal or digest already exists.",
    )


def _tokens(text: str) -> set[str]:
    return set(_TERMS.findall(text.lower()))


def _hypothesis_hits(
    db: Session, query: str, failures_only: bool = False
) -> list[dict]:
    query_terms = _tokens(query)
    hits: list[dict] = []
    for hypothesis in db.scalars(select(ResearchHypothesis)).all():
        question = str(hypothesis.specification.get("research_question", ""))
        terms = _tokens(question + " " + hypothesis.trial_family)
        score = len(query_terms & terms) / max(1, len(query_terms))
        if score == 0:
            continue
        outcomes = db.scalars(
            select(ResearchResult.outcome)
            .join(ResearchTrial, ResearchResult.trial_id == ResearchTrial.id)
            .join(
                ResearchExperiment, ResearchTrial.experiment_id == ResearchExperiment.id
            )
            .where(ResearchExperiment.hypothesis_id == hypothesis.id)
        ).all()
        if failures_only and not set(outcomes) & {"rejected", "failed", "inconclusive"}:
            continue
        decisions = db.scalars(
            select(ResearchDecision.decision)
            .join(ResearchResult, ResearchDecision.result_id == ResearchResult.id)
            .join(ResearchTrial, ResearchResult.trial_id == ResearchTrial.id)
            .join(
                ResearchExperiment, ResearchTrial.experiment_id == ResearchExperiment.id
            )
            .where(ResearchExperiment.hypothesis_id == hypothesis.id)
        ).all()
        hits.append(
            {
                "hypothesis_id": hypothesis.id,
                "hypothesis_key": hypothesis.hypothesis_key,
                "trial_family": hypothesis.trial_family,
                "research_question": question,
                "score": round(score, 6),
                "outcomes": list(outcomes),
                "decisions": list(decisions),
            }
        )
    return sorted(hits, key=lambda item: (-item["score"], item["hypothesis_key"]))[:10]


def search_knowledge(
    db: Session, query: str, limit: int, evidence_types: list[str]
) -> dict:
    query_terms = _tokens(query)
    statement = select(ResearchChunk, ResearchDocument).join(
        ResearchDocument, ResearchChunk.document_id == ResearchDocument.id
    )
    if evidence_types:
        statement = statement.where(ResearchDocument.evidence_type.in_(evidence_types))
    passages = []
    for chunk, document in db.execute(statement).all():
        text_terms = _tokens(chunk.text)
        section_terms = _tokens(chunk.section)
        lexical = len(query_terms & text_terms) / max(1, len(query_terms))
        structured = len(query_terms & section_terms) / max(1, len(query_terms))
        score = lexical + (0.35 * structured)
        if score <= 0:
            continue
        passages.append(
            {
                "chunk_id": chunk.id,
                "document_key": document.document_key,
                "title": document.title,
                "evidence_type": document.evidence_type,
                "section": chunk.section,
                "page": chunk.page,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "text": chunk.text,
                "text_digest": chunk.text_digest,
                "score": round(score, 6),
                "citation": f"{document.document_key}#{chunk.ordinal} lines {chunk.line_start}-{chunk.line_end} sha256:{chunk.text_digest}",
            }
        )
    passages.sort(
        key=lambda item: (-item["score"], item["document_key"], item["line_start"])
    )
    return {
        "query": query,
        "corpus_digest": corpus_digest(db),
        "passages": passages[:limit],
        "similar_hypotheses": _hypothesis_hits(db, query),
        "prior_failures": _hypothesis_hits(db, query, failures_only=True),
    }


def evaluate_retrieval(
    db: Session, payload: RetrievalEvaluationCreate
) -> ResearchRetrievalEvaluation:
    cases = []
    passed_count = 0
    for case in payload.cases:
        result = search_knowledge(db, case.question, 10, [])
        keys = {hit["document_key"] for hit in result["passages"]}
        text = " ".join(hit["text"].lower() for hit in result["passages"])
        passed = bool(keys & set(case.expected_document_keys)) and all(
            term.lower() in text for term in case.expected_terms
        )
        passed_count += int(passed)
        cases.append(
            {
                "question": case.question,
                "passed": passed,
                "returned_document_keys": sorted(keys),
            }
        )
    recall = passed_count / len(payload.cases)
    report = {
        "case_count": len(cases),
        "passed_count": passed_count,
        "recall": recall,
        "minimum_recall": payload.minimum_recall,
        "cases": cases,
    }
    question_set_digest = record_digest(
        [case.model_dump(mode="json") for case in payload.cases]
    )
    document = {
        "evaluation_key": payload.evaluation_key,
        "corpus_digest": corpus_digest(db),
        "question_set_digest": question_set_digest,
        "report": report,
        "passed": recall >= payload.minimum_recall,
        "evaluated_by": payload.evaluated_by,
    }
    return _commit(
        db,
        ResearchRetrievalEvaluation(**document, record_digest=record_digest(document)),
        "Evaluation key or digest already exists.",
    )


def create_brief(db: Session, payload: ResearchBriefCreate) -> ResearchBrief:
    current_corpus = corpus_digest(db)
    evaluation = db.scalar(
        select(ResearchRetrievalEvaluation)
        .where(
            ResearchRetrievalEvaluation.corpus_digest == current_corpus,
            ResearchRetrievalEvaluation.passed.is_(True),
        )
        .order_by(ResearchRetrievalEvaluation.evaluated_at.desc())
    )
    if evaluation is None:
        raise HTTPException(
            status_code=409,
            detail="A passing retrieval evaluation for the current corpus is required.",
        )
    cited_ids = {
        chunk_id for claim in payload.claims for chunk_id in claim.citation_chunk_ids
    }
    existing = (
        set(
            db.scalars(
                select(ResearchChunk.id).where(ResearchChunk.id.in_(cited_ids))
            ).all()
        )
        if cited_ids
        else set()
    )
    if existing != cited_ids:
        raise HTTPException(
            status_code=422, detail="Brief contains an unknown passage citation."
        )
    prior_result_ids = {
        chunk_id
        for claim in payload.claims
        if claim.evidence_class == "prior_result"
        for chunk_id in claim.citation_chunk_ids
    }
    if prior_result_ids:
        classified = set(
            db.scalars(
                select(ResearchChunk.id)
                .join(
                    ResearchDocument,
                    ResearchChunk.document_id == ResearchDocument.id,
                )
                .where(
                    ResearchChunk.id.in_(prior_result_ids),
                    ResearchDocument.evidence_type == "prior_result",
                )
            ).all()
        )
        if classified != prior_result_ids:
            raise HTTPException(
                status_code=422,
                detail="Prior-result claims must cite prior-result passages.",
            )
    brief = {
        "summary": payload.summary,
        "claims": [claim.model_dump(mode="json") for claim in payload.claims],
    }
    document = {
        "question": payload.question,
        "corpus_digest": current_corpus,
        "evaluation_id": str(evaluation.id),
        "brief": brief,
        "created_by": payload.created_by,
    }
    return _commit(
        db,
        ResearchBrief(
            question=payload.question,
            corpus_digest=current_corpus,
            evaluation_id=evaluation.id,
            brief=brief,
            record_digest=record_digest(document),
            created_by=payload.created_by,
        ),
        "Brief digest already exists.",
    )
