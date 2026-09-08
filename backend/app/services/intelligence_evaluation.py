import hashlib
import json
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intelligence_evaluation import (
    IntelligenceEvaluationItemResult,
    IntelligenceEvaluationRun,
    IntelligenceEvaluationSuite,
)
from app.schemas.intelligence_evaluation import (
    IntelligenceRunCreate,
    IntelligenceSuiteCreate,
)


class IntelligenceEvaluationConflict(ValueError):
    pass


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


METRICS = (
    "citation_entailment",
    "answer_completeness",
    "unsupported_claim_control",
    "abstention_calibration",
    "formula_accuracy",
    "table_accuracy",
    "multi_hop_validity",
    "latency_compliance",
)


def applicable_metrics(gold: dict) -> set[str]:
    metrics = {
        "unsupported_claim_control",
        "abstention_calibration",
        "latency_compliance",
    }
    if gold["required_citation_digests"]:
        metrics.add("citation_entailment")
    if gold["required_answer_tokens"]:
        metrics.add("answer_completeness")
    if gold["formula_digest"]:
        metrics.add("formula_accuracy")
    if gold["table_digest"]:
        metrics.add("table_accuracy")
    if gold["path_edge_digests"]:
        metrics.add("multi_hop_validity")
    return metrics


def score_response(gold: dict, response, thresholds: dict) -> tuple[dict, list[str]]:
    required_tokens = set(gold["required_answer_tokens"])
    supported = set(gold["supported_claim_digests"])
    scores = {
        "citation_entailment": float(
            set(gold["required_citation_digests"]).issubset(response.citation_digests)
        ),
        "answer_completeness": (
            len(required_tokens & set(response.answer_tokens)) / len(required_tokens)
            if required_tokens
            else 1.0
        ),
        "unsupported_claim_control": (
            1.0
            if not response.claim_digests
            else len(set(response.claim_digests) & supported)
            / len(set(response.claim_digests))
        ),
        "abstention_calibration": float(response.abstained == gold["must_abstain"]),
        "formula_accuracy": float(
            not gold["formula_digest"]
            or response.formula_digest == gold["formula_digest"]
        ),
        "table_accuracy": float(
            not gold["table_digest"] or response.table_digest == gold["table_digest"]
        ),
        "multi_hop_validity": float(
            response.path_edge_digests == gold["path_edge_digests"]
        ),
        "latency_compliance": float(
            response.latency_ms <= int(thresholds.get("maximum_latency_ms", 5000))
        ),
    }
    failures = [
        key
        for key, value in scores.items()
        if key in applicable_metrics(gold) and value < thresholds.get(key, 1.0)
    ]
    return scores, failures


def register_suite(
    db: Session, payload: IntelligenceSuiteCreate
) -> IntelligenceEvaluationSuite:
    material = payload.model_dump(mode="json")
    record_digest = _digest(material)
    existing = db.scalar(
        select(IntelligenceEvaluationSuite).where(
            IntelligenceEvaluationSuite.suite_version == payload.suite_version
        )
    )
    if existing:
        if existing.record_digest != record_digest:
            raise IntelligenceEvaluationConflict(
                "Evaluation suite version is immutable."
            )
        return existing
    public = [
        {
            "item_key": i.item_key,
            "domain": i.domain,
            "task_type": i.task_type,
            "prompt_digest": i.prompt_digest,
        }
        for i in payload.items
    ]
    record = IntelligenceEvaluationSuite(
        suite_version=payload.suite_version,
        scope=payload.scope,
        corpus_digest=payload.corpus_digest,
        projection_digest=payload.projection_digest,
        item_manifest=public,
        hidden_gold=[i.model_dump(mode="json") for i in payload.items],
        thresholds=payload.thresholds,
        record_digest=record_digest,
        created_by=payload.created_by,
    )
    db.add(record)
    db.flush()
    return record


def evaluate_run(
    db: Session, payload: IntelligenceRunCreate
) -> IntelligenceEvaluationRun:
    suite = db.get(IntelligenceEvaluationSuite, payload.suite_id)
    if not suite:
        raise IntelligenceEvaluationConflict("Evaluation suite not found.")
    if payload.evaluator_id == suite.created_by:
        raise IntelligenceEvaluationConflict(
            "Suite producer cannot evaluate its own suite."
        )
    response_map = {item.item_key: item for item in payload.responses}
    if len(response_map) != len(payload.responses):
        raise IntelligenceEvaluationConflict("Response item keys must be unique.")
    gold_keys = {item["item_key"] for item in suite.hidden_gold}
    if set(response_map) != gold_keys:
        raise IntelligenceEvaluationConflict(
            "Responses must cover the exact hidden suite manifest."
        )
    response_digest = _digest(
        [item.model_dump(mode="json") for item in payload.responses]
    )
    stale = (
        payload.corpus_digest != suite.corpus_digest
        or payload.projection_digest != suite.projection_digest
    )
    results, aggregate, per_domain = [], defaultdict(list), defaultdict(list)
    for gold in suite.hidden_gold:
        response = response_map[gold["item_key"]]
        scores, failures = score_response(gold, response, suite.thresholds)
        if stale:
            failures.append("stale_evidence")
        passed = not failures
        for key in applicable_metrics(gold):
            aggregate[key].append(scores[key])
        per_domain[gold["domain"]].append(passed)
        results.append((gold, response, scores, failures, passed))
    metrics = {key: sum(values) / len(values) for key, values in aggregate.items()}
    domains = {
        domain: {
            "items": len(values),
            "passed": sum(values),
            "status": "qualified" if all(values) and not stale else "not_demonstrated",
        }
        for domain, values in per_domain.items()
    }
    previous = db.scalar(
        select(IntelligenceEvaluationRun)
        .where(IntelligenceEvaluationRun.suite_id == suite.id)
        .order_by(IntelligenceEvaluationRun.created_at.desc())
    )
    regression_tolerance = suite.thresholds.get("maximum_metric_regression", 0)
    regressions = (
        [
            key
            for key in METRICS
            if key in previous.metrics
            and key in metrics
            and previous.metrics[key] - metrics[key] > regression_tolerance
        ]
        if previous
        else []
    )
    qualified = (
        not stale
        and not regressions
        and all(
            metrics.get(key, 0) >= value
            for key, value in suite.thresholds.items()
            if key in METRICS
        )
        and all(v["status"] == "qualified" for v in domains.values())
    )
    limitations = (["corpus_or_projection_digest_stale"] if stale else []) + [
        f"metric_below_threshold:{key}"
        for key in METRICS
        if metrics.get(key, 0) < suite.thresholds.get(key, 1.0)
    ] + [f"metric_regression:{key}" for key in regressions]
    material = {
        "suite_digest": suite.record_digest,
        "response_digest": response_digest,
        "corpus_digest": payload.corpus_digest,
        "projection_digest": payload.projection_digest,
        "model_runtime_digest": payload.model_runtime_digest,
        "evaluator_id": payload.evaluator_id,
        "metrics": metrics,
        "domains": domains,
        "limitations": limitations,
    }
    evaluation_digest = _digest(material)
    existing = db.scalar(
        select(IntelligenceEvaluationRun).where(
            IntelligenceEvaluationRun.evaluation_digest == evaluation_digest
        )
    )
    if existing:
        return existing
    run = IntelligenceEvaluationRun(
        id=uuid.uuid4(),
        suite_id=suite.id,
        corpus_digest=payload.corpus_digest,
        projection_digest=payload.projection_digest,
        model_runtime_digest=payload.model_runtime_digest,
        evaluator_id=payload.evaluator_id,
        status="qualified" if qualified else ("stale" if stale else "not_qualified"),
        metrics=metrics,
        domain_results=domains,
        limitations=limitations,
        response_digest=response_digest,
        evaluation_digest=evaluation_digest,
    )
    db.add(run)
    db.flush()
    for gold, response, scores, failures, passed in results:
        evidence = response.model_dump(mode="json")
        db.add(
            IntelligenceEvaluationItemResult(
                run_id=run.id,
                item_key=gold["item_key"],
                domain=gold["domain"],
                task_type=gold["task_type"],
                passed=passed,
                scores=scores,
                failure_reasons=failures,
                response_evidence=evidence,
                result_digest=_digest(
                    {
                        "run": str(run.id),
                        "item": gold["item_key"],
                        "evidence": evidence,
                        "scores": scores,
                        "failures": failures,
                    }
                ),
            )
        )
    db.flush()
    return run


def readiness(db: Session) -> dict:
    suite = db.scalar(
        select(IntelligenceEvaluationSuite).order_by(
            IntelligenceEvaluationSuite.created_at.desc()
        )
    )
    if not suite:
        return {
            "status": "not_demonstrated",
            "domains": {},
            "limitations": ["no_evaluation_suite"],
        }
    run = db.scalar(
        select(IntelligenceEvaluationRun)
        .where(IntelligenceEvaluationRun.suite_id == suite.id)
        .order_by(IntelligenceEvaluationRun.created_at.desc())
    )
    if not run:
        domains = {
            item["domain"]: {"status": "not_demonstrated"}
            for item in suite.item_manifest
        }
        return {
            "status": "not_demonstrated",
            "suite_digest": suite.record_digest,
            "domains": domains,
            "limitations": ["no_evaluation_run"],
        }
    failures = list(
        db.scalars(
            select(IntelligenceEvaluationItemResult)
            .where(
                IntelligenceEvaluationItemResult.run_id == run.id,
                IntelligenceEvaluationItemResult.passed.is_(False),
            )
            .order_by(IntelligenceEvaluationItemResult.item_key)
            .limit(10)
        ).all()
    )
    limitations = list(run.limitations)
    if suite.scope != "live_corpus":
        limitations.append("contract_fixture_does_not_demonstrate_live_intelligence")
    return {
        "status": run.status if suite.scope == "live_corpus" else "contract_validated",
        "scope": suite.scope,
        "suite_digest": suite.record_digest,
        "evaluation_digest": run.evaluation_digest,
        "model_runtime_digest": run.model_runtime_digest,
        "domains": run.domain_results,
        "metrics": run.metrics,
        "limitations": limitations,
        "representative_failures": [
            {
                "item_key": item.item_key,
                "domain": item.domain,
                "task_type": item.task_type,
                "failure_reasons": item.failure_reasons,
                "result_digest": item.result_digest,
            }
            for item in failures
        ],
        "claim_boundary": (
            "Qualification applies only to this exact live corpus, projection, "
            "model runtime and hidden suite; absent domains remain not demonstrated."
            if suite.scope == "live_corpus"
            else "The evaluator contract passed synthetic fixtures; live institutional "
            "intelligence is not demonstrated."
        ),
    }
