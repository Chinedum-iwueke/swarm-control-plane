from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.models import (
    ResearchDataSnapshot,
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchResult,
    ResearchReview,
    ResearchSource,
    ResearchTrial,
)
from app.models.alpha_discovery import AlphaDiscoveryCandidate
from app.services.research_evidence import publish_research_record

NOW = datetime(2026, 11, 12, tzinfo=UTC)
IDS = [UUID(f"10000000-0000-4000-8000-{index:012d}") for index in range(1, 10)]
DIGESTS = [f"{index:x}" * 64 for index in range(1, 10)]


def test_research_lifecycle_publishes_canonical_objects_and_typed_edges() -> None:
    source = ResearchSource(
        id=IDS[0],
        source_key="source-1",
        specification={
            "title": "Point-in-time market data",
            "source_type": "dataset",
            "version": "v1",
            "content_sha256": DIGESTS[0],
            "provenance": "governed lake",
            "point_in_time": True,
            "observed_at": NOW.isoformat(),
        },
        record_digest=DIGESTS[0],
        registered_by="research-registry",
        registered_at=NOW,
    )
    snapshot = ResearchDataSnapshot(
        id=IDS[1], source_id=source.id, snapshot_key="snapshot-1",
        specification={"provider": "bybit", "instrument": "BTCUSDT"},
        content_digest=DIGESTS[1], record_digest=DIGESTS[1],
        registered_by="research-registry", registered_at=NOW,
    )
    hypothesis = ResearchHypothesis(
        id=IDS[2], hypothesis_key="hypothesis-1", trial_family="family-1",
        specification={
            "research_question": "Does lagged return predict forward return after costs?",
            "rationale": "Slow diffusion may create measurable price persistence.",
            "mechanism": "Market participants incorporate information at different speeds.",
            "prediction": "Positive lagged return predicts positive forward return.",
            "universe": ["BTCUSDT"], "target": "forward return", "horizon": "one hour",
            "null_hypothesis": "Conditional forward return is not positive after costs.",
            "failure_conditions": ["non-positive out-of-sample effect"],
            "rival_explanations": ["regime imbalance"], "maximum_trials": 8,
        },
        record_digest=DIGESTS[2], registered_by="senior-researcher", registered_at=NOW,
    )
    experiment = ResearchExperiment(
        id=IDS[3], experiment_key="experiment-1", hypothesis_id=hypothesis.id,
        source_id=source.id, snapshot_id=snapshot.id,
        manifest={"repository": "bulletproof_bt", "repository_commit": "a" * 40},
        manifest_digest=DIGESTS[3], registered_by="strategy-engineer", registered_at=NOW,
    )
    trial = ResearchTrial(
        id=IDS[4], experiment_id=experiment.id, trial_family="family-1",
        run_id="run-1", trial_number=1,
        plan={"code_commit": "b" * 40, "engine_digest": DIGESTS[4]},
        record_digest=DIGESTS[4], executed_by="research-runner", registered_at=NOW,
    )
    result = ResearchResult(
        id=IDS[5], trial_id=trial.id, outcome="rejected",
        result={"metrics": {"oos_sharpe": -0.2}}, record_digest=DIGESTS[5],
        recorded_by="research-runner", recorded_at=NOW,
    )
    review = ResearchReview(
        id=IDS[6], subject_type="result", subject_id=result.id,
        subject_digest=result.record_digest, review_kind="independent_review",
        verdict="rejected", review={"reason": "failed preregistered gate"},
        record_digest=DIGESTS[6], reviewer="independent-reviewer", reviewed_at=NOW,
    )
    decision = ResearchDecision(
        id=IDS[7], result_id=result.id, decision="reject",
        rationale="The preregistered out-of-sample gate failed.",
        result_digest=result.record_digest, record_digest=DIGESTS[7],
        decided_by="research-director", decided_at=NOW,
    )
    candidate = AlphaDiscoveryCandidate(
        id=IDS[8], cycle_id=IDS[0], candidate_key="candidate-1",
        question="Does lagged return predict forward return after costs?",
        document={
            "title": "Lagged return continuation candidate",
            "predictor": "lagged return", "target": "forward return", "horizon": "one hour",
            "causal_timing": "The predictor closes before the target interval begins.",
            "null_hypothesis": "Conditional forward return is not positive after costs.",
            "predicted_direction": "positive",
            "mechanism": "Market participants incorporate information at different speeds.",
            "rival_explanations": ["regime imbalance"],
            "falsification_criteria": ["non-positive out-of-sample effect"],
            "data": {"venue": "bybit", "instruments": ["BTCUSDT"], "timeframe": "1m"},
            "parameter_budget": {"maximum_variants": 8, "parameter_names": ["lookback"]},
            "representation_plan": None, "evidence_object_ids": [source.id],
        },
        disposition="accepted", reason_codes=[], candidate_digest=DIGESTS[8], created_at=NOW,
    )
    records = [source, snapshot, hypothesis, experiment, trial, result, review, decision, candidate]
    lookup = {item.id: item for item in records}
    db = MagicMock()
    db.get.side_effect = lambda _model, object_id: lookup.get(object_id)

    with patch("app.services.research_evidence.register_evidence_object") as objects, patch(
        "app.services.research_evidence.register_edge"
    ) as edges:
        for record in records:
            publish_research_record(db, record)

    assert [call.args[1].object_type for call in objects.call_args_list] == [
        "source", "dataset", "hypothesis", "method", "run", "result", "review", "decision",
        "research_candidate",
    ]
    predicates = [call.args[1].predicate for call in edges.call_args_list]
    assert predicates == [
        "uses_method", "uses_dataset", "uses_method", "uses_dataset",
        "belongs_to_trial_family", "produced_result", "belongs_to_trial_family",
        "reviews", "decides_on",
    ]
    assert all(call.kwargs["commit"] is False for call in edges.call_args_list)
