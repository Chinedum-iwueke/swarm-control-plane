import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.research import (
    DataSnapshotSpecification,
    ExperimentManifest,
    HypothesisSpecification,
    ResearchDataSnapshotCreate,
    ResearchDecisionCreate,
    ResearchHypothesisCreate,
    ResearchResultCreate,
    ResearchReviewCreate,
    ResearchSourceCreate,
    ResearchTrialCreate,
    ResultDocument,
    SourceSpecification,
    TrialPlan,
)
from app.services.research import (
    add_review,
    record_digest,
    register_data_snapshot,
    register_decision,
    register_hypothesis,
    register_result,
    register_source,
    register_trial,
)

DIGEST = "a" * 64
ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime(2026, 7, 31, tzinfo=UTC)


def hypothesis_spec(maximum_trials: int = 1) -> HypothesisSpecification:
    return HypothesisSpecification(
        research_question="Does lagged return predict the next return after costs?",
        rationale="Momentum persistence is a plausible behavioral market effect.",
        mechanism="Slow information diffusion can cause prices to adjust gradually.",
        prediction="Positive lagged return predicts positive next-period return.",
        universe=["synthetic-regime-v1"],
        target="next-period return",
        horizon="one bar",
        null_hypothesis="Conditional forward return is not positive after costs.",
        failure_conditions=["out-of-sample Sharpe below one"],
        rival_explanations=["regime imbalance"],
        maximum_trials=maximum_trials,
    )


def trial_payload(experiment_digest: str = DIGEST) -> ResearchTrialCreate:
    plan = TrialPlan(
        run_id="M11-RUN-1",
        task_id=ID,
        code_commit="b" * 40,
        dataset_digest="c" * 64,
        engine_digest="d" * 64,
    )
    document = {
        "experiment_digest": experiment_digest,
        "trial_number": 1,
        "plan": plan.model_dump(mode="json"),
        "executed_by": "vm1-research-runner",
    }
    return ResearchTrialCreate(
        experiment_digest=experiment_digest,
        plan=plan,
        record_digest=record_digest(document),
        executed_by="vm1-research-runner",
    )


def test_contracts_reject_unknown_fields_and_invalid_date_range() -> None:
    document = hypothesis_spec().model_dump()
    document["result"] = "peeked"
    with pytest.raises(ValidationError):
        HypothesisSpecification.model_validate(document)
    with pytest.raises(ValidationError, match="date_end"):
        ExperimentManifest(
            repository="bulletproof_bt",
            repository_commit="a" * 40,
            dataset_version="snapshot-1",
            instrument_universe=["SPY"],
            timeframe="daily",
            date_start=date(2026, 1, 1),
            date_end=date(2025, 1, 1),
            features=["lagged-return"],
            target="forward return",
            model_or_rule="long when lagged return is positive",
            parameters={},
            fees_bps=5,
            slippage_bps=2,
            delay_bars=1,
            validation_method="purged walk-forward",
            success_criteria=["OOS Sharpe >= 1"],
            rejection_criteria=["cost stress failure"],
            engine_version="bulletproof-1",
        )


def test_hypothesis_digest_is_verified_before_registration() -> None:
    payload = ResearchHypothesisCreate(
        hypothesis_key="M11-H1",
        trial_family="momentum-daily-v1",
        specification=hypothesis_spec(),
        record_digest="0" * 64,
        registered_by="hypothesis-architect",
    )
    with pytest.raises(HTTPException, match="digest mismatch"):
        register_hypothesis(MagicMock(), payload)


def test_data_snapshot_is_source_bound_and_digest_verified() -> None:
    specification = DataSnapshotSpecification(
        provider="binance",
        instrument="BTCUSDT",
        timeframe="1h",
        date_start=NOW,
        date_end=datetime(2026, 8, 1, tzinfo=UTC),
        rows=8760,
        format="csv",
        storage_uri="worker/research-data/m13/snapshot.csv",
        transformation="Pinned UTC hourly aggregation.",
        point_in_time=True,
    )
    payload = ResearchDataSnapshotCreate(
        snapshot_key="M13-BTC-1H",
        source_id=ID,
        specification=specification,
        content_digest="b" * 64,
        record_digest="0" * 64,
        registered_by="research-registry",
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(id=ID)
    with pytest.raises(HTTPException, match="digest mismatch"):
        register_data_snapshot(db, payload)


def test_valid_source_is_committed_and_returned() -> None:
    specification = SourceSpecification(
        title="Pinned M13 BTC snapshot",
        source_type="dataset",
        version="M13-BINANCE-BTCUSDT-1H-2025",
        content_sha256="b" * 64,
        provenance="Derived from the canonical point-in-time market-data store.",
        point_in_time=True,
        observed_at=NOW,
    )
    payload = ResearchSourceCreate(
        source_key="M13-BTC-SOURCE-1",
        specification=specification,
        record_digest=record_digest(specification),
        registered_by="research-registry",
    )
    db = MagicMock()

    record = register_source(db, payload)

    assert record.source_key == payload.source_key
    assert record.record_digest == payload.record_digest
    db.add.assert_called_once_with(record)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(record)


def test_trial_requires_exact_approved_manifest() -> None:
    experiment = SimpleNamespace(
        id=ID,
        hypothesis_id=ID,
        manifest_digest=DIGEST,
    )
    hypothesis = SimpleNamespace(
        trial_family="momentum-daily-v1",
        specification={"maximum_trials": 1},
    )
    db = MagicMock()
    db.get.side_effect = lambda model, _: (
        experiment if model.__name__ == "ResearchExperiment" else hypothesis
    )
    db.scalar.return_value = None
    with pytest.raises(HTTPException, match="not approved"):
        register_trial(db, ID, trial_payload())


def test_trial_family_budget_counts_every_attempt() -> None:
    experiment = SimpleNamespace(id=ID, hypothesis_id=ID, manifest_digest=DIGEST)
    hypothesis = SimpleNamespace(
        trial_family="momentum-daily-v1",
        specification={"maximum_trials": 1},
    )
    db = MagicMock()
    db.get.side_effect = lambda model, _: (
        experiment if model.__name__ == "ResearchExperiment" else hypothesis
    )
    db.scalar.side_effect = [ID, 1]
    with pytest.raises(HTTPException, match="budget is exhausted"):
        register_trial(db, ID, trial_payload())


def test_failed_and_negative_results_are_registered() -> None:
    trial = SimpleNamespace(id=ID, record_digest=DIGEST)
    db = MagicMock()
    db.get.return_value = trial
    db.refresh.side_effect = lambda record: setattr(record, "id", ID)
    result = ResultDocument(
        summary="The predeclared hypothesis failed its out-of-sample gate.",
        metrics={"oos_sharpe": -0.2},
        robustness_status="failed",
        rejection_reason="Out-of-sample Sharpe was below the locked threshold.",
        evidence_artifacts=["research-evidence.json"],
        output_artifact_digest="e" * 64,
        started_at=NOW,
        ended_at=NOW,
    )
    document = {
        "trial_digest": DIGEST,
        "outcome": "rejected",
        "result": result.model_dump(mode="json"),
        "recorded_by": "vm1-research-runner",
    }
    payload = ResearchResultCreate(
        trial_digest=DIGEST,
        outcome="rejected",
        result=result,
        record_digest=record_digest(document),
        recorded_by="vm1-research-runner",
    )
    registered = register_result(db, ID, payload)
    assert registered.outcome == "rejected"
    db.add.assert_called_once()


def test_result_review_must_be_independent() -> None:
    result = SimpleNamespace(id=ID, trial_id=ID, record_digest=DIGEST)
    trial = SimpleNamespace(executed_by="vm1-research-runner")
    db = MagicMock()
    db.get.side_effect = [result, trial]
    review = ResearchReviewCreate(
        subject_digest=DIGEST,
        review_kind="independent_review",
        verdict="approved",
        review={"summary": "Reproduced independently."},
        reviewer="vm1-research-runner",
    )
    with pytest.raises(HTTPException, match="independent"):
        add_review(db, "result", ID, review)


def test_decision_requires_two_distinct_reviewers() -> None:
    result = SimpleNamespace(id=ID, record_digest=DIGEST)
    db = MagicMock()
    db.get.return_value = result
    db.execute.return_value.all.return_value = [
        ("independent_review", "same-reviewer"),
        ("adversarial_review", "same-reviewer"),
    ]
    payload = ResearchDecisionCreate(
        result_digest=DIGEST,
        decision="retain",
        rationale="Retain the complete result as institutional evidence.",
        decided_by="founder-operator",
    )
    with pytest.raises(HTTPException, match="different agents"):
        register_decision(db, ID, payload)


def test_migration_enforces_database_level_append_only_records() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic/versions/b2c4d6e8f110_add_immutable_research_registry.py"
    ).read_text(encoding="utf-8")
    assert "BEFORE UPDATE OR DELETE" in migration
    for table in (
        "research_sources",
        "research_hypotheses",
        "research_experiments",
        "research_reviews",
        "research_trials",
        "research_results",
        "research_decisions",
    ):
        assert table in migration


def test_digest_is_canonical_and_secret_free() -> None:
    first = record_digest({"b": 2, "a": 1})
    second = record_digest({"a": 1, "b": 2})
    assert first == second == hashlib.sha256(b'{"a":1,"b":2}').hexdigest()
    assert "password" not in first
