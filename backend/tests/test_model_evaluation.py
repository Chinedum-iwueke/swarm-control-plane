from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.model_evaluations import router
from app.schemas.model_evaluation import ModelFamilyEvaluationCreate
from app.services.model_evaluation import (
    ModelEvaluationConflict,
    build_scorecard,
    register_evaluation,
)
from app.services.research import record_digest

MATERIALIZATION_ID = uuid4()
AUDIT_ID = uuid4()


def candidate(
    key,
    family,
    score,
    *,
    baseline_kind=None,
    permutation=0.5,
    low_regime=None,
    minority=40,
):
    regimes = [
        {
            "regime": "trend",
            "observations": 100,
            "positive_labels": minority,
            "negative_labels": 100 - minority,
            "primary_score": score if low_regime is None else low_regime,
        },
        {
            "regime": "range",
            "observations": 100,
            "positive_labels": minority,
            "negative_labels": 100 - minority,
            "primary_score": score - 0.02,
        },
    ]
    return {
        "candidate_key": key,
        "family": family,
        "baseline_kind": baseline_kind,
        "model_bundle_digest": record_digest({"model": key}),
        "predictions_digest": record_digest({"predictions": key}),
        "overall_primary_score": score,
        "permutation_primary_score": permutation,
        "fold_metrics": [
            {
                "fold": 1,
                "observations": 100,
                "primary_score": score - 0.01,
                "log_loss": 0.6,
                "brier_score": 0.22,
            },
            {
                "fold": 2,
                "observations": 100,
                "primary_score": score + 0.01,
                "log_loss": 0.59,
                "brier_score": 0.21,
            },
        ],
        "regime_metrics": regimes,
    }


def payload(candidates=None, **protocol_updates):
    protocol = {
        "schema_version": "model-family-regime-evaluation-v1.0.0",
        "primary_metric": "balanced_accuracy",
        "minimum_incremental_value": 0.03,
        "minimum_regime_score": 0.55,
        "maximum_regime_dispersion": 0.15,
        "maximum_permutation_score": 0.52,
        "minimum_regime_observations": 50,
        "minimum_minority_fraction": 0.2,
        "required_regimes": ["trend", "range"],
        "action_authority": False,
    }
    protocol.update(protocol_updates)
    candidates = candidates or [
        candidate("unconditional", "baseline", 0.50, baseline_kind="unconditional"),
        candidate("linear", "baseline", 0.54, baseline_kind="linear"),
        candidate("supervised", "supervised", 0.64),
        candidate("unsupervised", "unsupervised", 0.56),
        candidate("regime", "regime", 0.66),
        candidate("meta", "meta_label", 0.63),
    ]
    return ModelFamilyEvaluationCreate.model_validate(
        {
            "evaluation_key": "ML003-PILOT",
            "materialization_id": MATERIALIZATION_ID,
            "selection_audit_id": AUDIT_ID,
            "protocol": protocol,
            "protocol_digest": record_digest(protocol),
            "candidates": candidates,
            "candidates_digest": record_digest(candidates),
            "evaluated_by": "ml003-pilot",
        }
    )


def records():
    materialization = SimpleNamespace(
        id=MATERIALIZATION_ID,
        record_digest="a" * 64,
        fold_results=[{"fold": 1}, {"fold": 2}],
    )
    audit = SimpleNamespace(
        id=AUDIT_ID,
        audit_digest="b" * 64,
        status="active",
        conclusion="selection_adjusted",
    )
    return materialization, audit


def test_scorecard_ranks_and_qualifies_incremental_stable_families():
    materialization, audit = records()
    scorecard = build_scorecard(payload(), materialization, audit)
    assert scorecard["strongest_baseline_score"] == 0.54
    assert scorecard["ranking"][0]["candidate_key"] == "regime"
    assert set(scorecard["qualified_candidate_keys"]) == {
        "supervised",
        "regime",
        "meta",
    }
    assert scorecard["promotion_authority"] is False


def test_complete_baseline_ladder_is_required():
    values = payload().candidates
    incomplete = [
        item.model_dump(mode="json")
        for item in values
        if item.baseline_kind != "linear"
    ]
    with pytest.raises(ModelEvaluationConflict, match="linear baselines"):
        materialization, audit = records()
        build_scorecard(payload(incomplete), materialization, audit)


def test_label_permutation_failure_is_retained_not_qualified():
    values = [item.model_dump(mode="json") for item in payload().candidates]
    next(item for item in values if item["candidate_key"] == "supervised")[
        "permutation_primary_score"
    ] = 0.60
    materialization, audit = records()
    row = next(
        item
        for item in build_scorecard(payload(values), materialization, audit)["ranking"]
        if item["candidate_key"] == "supervised"
    )
    assert row["qualified"] is False
    assert "label_permutation_control_failed" in row["reasons"]


def test_unstable_regime_and_class_imbalance_are_rejected():
    values = [item.model_dump(mode="json") for item in payload().candidates]
    target = next(item for item in values if item["candidate_key"] == "regime")
    target["regime_metrics"][0]["primary_score"] = 0.40
    target["regime_metrics"][0]["positive_labels"] = 5
    target["regime_metrics"][0]["negative_labels"] = 95
    materialization, audit = records()
    row = next(
        item
        for item in build_scorecard(payload(values), materialization, audit)["ranking"]
        if item["candidate_key"] == "regime"
    )
    assert {
        "weak_regime",
        "unstable_across_regimes",
        "insufficient_class_support",
    }.issubset(row["reasons"])


def test_fold_and_regime_coverage_must_be_exact():
    values = [item.model_dump(mode="json") for item in payload().candidates]
    values[2]["fold_metrics"].pop()
    materialization, audit = records()
    with pytest.raises(ModelEvaluationConflict, match="every causal fold"):
        build_scorecard(payload(values), materialization, audit)


def test_registration_requires_current_nonblocked_audit():
    db = MagicMock()
    materialization, audit = records()
    audit.conclusion = "blocked"
    db.get.side_effect = [materialization, audit]
    with pytest.raises(ModelEvaluationConflict, match="non-blocked"):
        register_evaluation(db, payload())


def test_routes_are_registered():
    assert {route.path for route in router.routes} == {
        "/v1/research/model-evaluations",
        "/v1/research/model-evaluations/{evaluation_id}",
    }
