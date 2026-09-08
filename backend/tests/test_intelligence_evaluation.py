import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from app.api.routes.intelligence_evaluation import _suite_response
from app.schemas.intelligence_evaluation import (
    IntelligenceResponse,
    IntelligenceRunCreate,
    IntelligenceSuiteCreate,
)
from app.services.intelligence_evaluation import (
    IntelligenceEvaluationConflict,
    applicable_metrics,
    evaluate_run,
    score_response,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def gold(**overrides):
    value = {
        "required_citation_digests": [sha("citation")],
        "required_answer_tokens": ["alpha", "beta"],
        "supported_claim_digests": [sha("claim")],
        "formula_digest": sha("formula"),
        "table_digest": sha("table"),
        "path_edge_digests": [sha("edge-1"), sha("edge-2")],
        "must_abstain": False,
    }
    value.update(overrides)
    return value


def response(**overrides):
    value = {
        "item_key": "item-1",
        "answer_tokens": ["alpha", "beta"],
        "citation_digests": [sha("citation")],
        "claim_digests": [sha("claim")],
        "formula_digest": sha("formula"),
        "table_digest": sha("table"),
        "path_edge_digests": [sha("edge-1"), sha("edge-2")],
        "abstained": False,
        "latency_ms": 200,
    }
    value.update(overrides)
    return IntelligenceResponse.model_validate(value)


def test_exact_evidence_bound_response_passes_all_metrics():
    scores, failures = score_response(gold(), response(), {"maximum_latency_ms": 500})
    assert set(scores.values()) == {1.0}
    assert failures == []


def test_non_applicable_formula_table_and_path_do_not_inflate_aggregates():
    item = gold(formula_digest=None, table_digest=None, path_edge_digests=[])
    assert applicable_metrics(item) == {
        "citation_entailment",
        "answer_completeness",
        "unsupported_claim_control",
        "abstention_calibration",
        "latency_compliance",
    }


def test_suite_requires_a_complete_bounded_threshold_contract():
    with pytest.raises(ValueError, match="missing score thresholds"):
        IntelligenceSuiteCreate(
            suite_version="incomplete-v1",
            scope="live_corpus",
            corpus_digest=sha("corpus"),
            projection_digest=sha("projection"),
            items=[
                {
                    "item_key": "item-1",
                    "domain": "causal-reasoning",
                    "task_type": "direct_citation",
                    "prompt_digest": sha("prompt"),
                }
            ],
            thresholds={"maximum_latency_ms": 500},
            created_by="independent-author",
        )


def test_unsupported_claim_and_wrong_path_fail_closed():
    scores, failures = score_response(
        gold(),
        response(
            claim_digests=[sha("unsupported")],
            path_edge_digests=[sha("edge-2"), sha("edge-1")],
        ),
        {"unsupported_claim_control": 1.0, "multi_hop_validity": 1.0},
    )
    assert scores["unsupported_claim_control"] == 0.0
    assert scores["multi_hop_validity"] == 0.0
    assert failures == ["unsupported_claim_control", "multi_hop_validity"]


@pytest.mark.parametrize("abstained,must_abstain", [(True, False), (False, True)])
def test_abstention_is_scored_against_gold(abstained, must_abstain):
    scores, failures = score_response(
        gold(must_abstain=must_abstain),
        response(abstained=abstained),
        {"abstention_calibration": 1.0},
    )
    assert scores["abstention_calibration"] == 0.0
    assert "abstention_calibration" in failures


def suite():
    item = {
        "item_key": "item-1",
        "domain": "causal-reasoning",
        "task_type": "multi_hop",
        "prompt_digest": sha("prompt"),
        **gold(),
    }
    return SimpleNamespace(
        id=uuid.uuid4(),
        created_by="suite-author",
        corpus_digest=sha("corpus"),
        projection_digest=sha("projection"),
        hidden_gold=[item],
        thresholds={
            key: 1.0
            for key in (
                "citation_entailment",
                "answer_completeness",
                "unsupported_claim_control",
                "abstention_calibration",
                "formula_accuracy",
                "table_accuracy",
                "multi_hop_validity",
                "latency_compliance",
            )
        }
        | {"maximum_latency_ms": 500},
        record_digest=sha("suite"),
    )


def run_payload(record, **overrides):
    values = {
        "suite_id": record.id,
        "corpus_digest": record.corpus_digest,
        "projection_digest": record.projection_digest,
        "model_runtime_digest": sha("runtime"),
        "evaluator_id": "independent-evaluator",
        "responses": [response()],
    }
    values.update(overrides)
    return IntelligenceRunCreate.model_validate(values)


def test_suite_author_cannot_evaluate_own_hidden_items():
    record = suite()
    db = MagicMock()
    db.get.return_value = record
    with pytest.raises(IntelligenceEvaluationConflict, match="cannot evaluate"):
        evaluate_run(db, run_payload(record, evaluator_id=record.created_by))


def test_digest_drift_records_stale_run_and_item_failure():
    record = suite()
    db = MagicMock()
    db.get.return_value = record
    db.scalar.return_value = None
    result = evaluate_run(db, run_payload(record, corpus_digest=sha("changed")))
    assert result.status == "stale"
    assert result.limitations == ["corpus_or_projection_digest_stale"]
    item_result = db.add.call_args_list[-1].args[0]
    assert item_result.passed is False
    assert "stale_evidence" in item_result.failure_reasons


def test_metric_regression_fails_readiness_closed():
    record = suite()
    record.thresholds["formula_accuracy"] = 0.0
    record.thresholds["maximum_metric_regression"] = 0.0
    previous = SimpleNamespace(metrics={"formula_accuracy": 1.0})
    db = MagicMock()
    db.get.return_value = record
    db.scalar.side_effect = [previous, None]
    result = evaluate_run(
        db,
        run_payload(record, responses=[response(formula_digest=sha("wrong"))]),
    )
    assert result.status == "not_qualified"
    assert "metric_regression:formula_accuracy" in result.limitations


def test_public_suite_response_never_exposes_hidden_gold():
    record = SimpleNamespace(
        id=uuid.uuid4(),
        suite_version="hidden-v1",
        scope="live_corpus",
        corpus_digest=sha("corpus"),
        projection_digest=sha("projection"),
        item_manifest=[{"item_key": "item-1"}],
        hidden_gold=[{"required_answer_tokens": ["secret"]}],
        thresholds={"citation_entailment": 1.0},
        record_digest=sha("suite"),
        created_by="independent-author",
        created_at=None,
    )
    public = _suite_response(record)
    assert "hidden_gold" not in public
    assert "secret" not in str(public)
