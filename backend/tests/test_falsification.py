from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.falsification import router
from app.schemas.falsification import (
    MechanismEvaluationCreate,
    MechanismEvaluationDocument,
    MechanismPlanCreate,
    MechanismPlanDocument,
)
from app.services.falsification import (
    FalsificationConflict,
    register_evaluation,
    register_plan,
)
from app.services.research import record_digest
from pydantic import ValidationError

NOW = datetime(2026, 8, 27, 12, tzinfo=UTC)
ALT = "volatility-confounding"


def plan_document(**updates) -> MechanismPlanDocument:
    value = {
        "schema_version": 1,
        "mechanism": "Reduced liquidity amplifies the price response to directional forced flow.",
        "scope": "BTC perpetual hourly observations under the admitted catalog.",
        "assumptions": ["Depth proxy preserves the ordering of latent liquidity."],
        "alternatives": [
            {
                "explanation_key": ALT,
                "claim": "The apparent effect is entirely volatility clustering.",
                "confounders": ["realized-volatility", "calendar-regime"],
            }
        ],
        "decisive_tests": [
            {
                "test_key": "matched-depth-test",
                "prediction": "The effect remains positive after matching volatility and calendar regime.",
                "null_expectation": "The conditional effect is indistinguishable from zero after matching.",
                "falsifies_when": "The confidence interval includes the declared material negative boundary.",
                "target_alternatives": [ALT],
                "analysis_digest": "a" * 64,
            }
        ],
        "dossier_ids": [uuid4()],
        "opposition_record_ids": [uuid4()],
        "evidence_cutoff": NOW,
    }
    value.update(updates)
    return MechanismPlanDocument.model_validate(value)


def evaluation_document(
    plan_digest: str, outcome="passed", rival="ruled_out", **updates
) -> MechanismEvaluationDocument:
    value = {
        "schema_version": 1,
        "plan_digest": plan_digest,
        "outcomes": [
            {
                "test_key": "matched-depth-test",
                "outcome": outcome,
                "observed_result": "The matched incremental estimate was retained with its uncertainty interval.",
                "evidence_object_id": uuid4(),
                "evidence_digest": "b" * 64,
                "rival_outcomes": {ALT: rival},
            }
        ],
        "evaluated_at": NOW + timedelta(hours=2),
        "limitations": ["One venue and one declared population."],
    }
    value.update(updates)
    return MechanismEvaluationDocument.model_validate(value)


def test_plan_rejects_tautological_decisive_test() -> None:
    same = "The measured conditional effect equals the preregistered threshold."
    with pytest.raises(ValidationError, match="must differ"):
        plan_document(
            decisive_tests=[
                {
                    "test_key": "tautology",
                    "prediction": same,
                    "null_expectation": same,
                    "falsifies_when": same,
                    "target_alternatives": [ALT],
                    "analysis_digest": "a" * 64,
                }
            ]
        )


def test_every_alternative_requires_decisive_coverage() -> None:
    with pytest.raises(ValidationError, match="every competing"):
        plan_document(
            alternatives=[
                {
                    "explanation_key": ALT,
                    "claim": "The apparent effect is entirely volatility clustering.",
                    "confounders": ["realized-volatility"],
                },
                {
                    "explanation_key": "calendar-confounding",
                    "claim": "The apparent effect is entirely a calendar artifact.",
                    "confounders": ["calendar-regime"],
                },
            ],
            decisive_tests=[
                {
                    "test_key": "wrong-target",
                    "prediction": "The primary prediction remains measurable in the declared sample.",
                    "null_expectation": "The primary prediction is zero in the declared sample.",
                    "falsifies_when": "The observed result crosses the registered rejection boundary.",
                    "target_alternatives": [ALT],
                    "analysis_digest": "a" * 64,
                }
            ],
        )


def test_plan_requires_active_mechanism_map_hypothesis_and_ri_provenance() -> None:
    document = plan_document()
    payload = MechanismPlanCreate(
        plan_key="DISC006-PLAN-R1",
        discovery_map_id=uuid4(),
        hypothesis_id=uuid4(),
        plan=document,
        plan_digest=record_digest(document),
        registered_by="disc006-pilot",
    )
    db = MagicMock()
    db.get.side_effect = [
        SimpleNamespace(status="active", stage="mechanism"),
        SimpleNamespace(),
    ]
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [SimpleNamespace()]),
        SimpleNamespace(all=lambda: [SimpleNamespace()]),
    ]
    record = register_plan(db, payload)
    assert record.plan_digest == payload.plan_digest


def evaluation_db(document: MechanismEvaluationDocument):
    plan = SimpleNamespace(
        id=uuid4(),
        plan_digest=document.plan_digest,
        registered_at=NOW,
        plan=plan_document().model_dump(mode="json"),
    )
    evidence = SimpleNamespace(content_digest="b" * 64)
    db = MagicMock()
    db.scalar.return_value = plan
    db.scalars.return_value.all.return_value = [evidence]
    return db


@pytest.mark.parametrize(
    ("outcome", "rival", "expected"),
    [
        ("passed", "ruled_out", "supported"),
        ("failed", "ruled_out", "falsified"),
        ("passed", "not_ruled_out", "unresolved"),
        ("inconclusive", "inconclusive", "unresolved"),
    ],
)
def test_conclusion_is_computed_and_failed_test_cannot_be_hidden(
    outcome, rival, expected
) -> None:
    plan_digest = "c" * 64
    document = evaluation_document(plan_digest, outcome, rival)
    payload = MechanismEvaluationCreate(
        evaluation_key=f"DISC006-{outcome}-{rival}",
        plan_id=uuid4(),
        evaluation=document,
        evaluation_digest=record_digest(document),
        evaluated_by="independent-reviewer",
    )
    record = register_evaluation(evaluation_db(document), payload)
    assert record.conclusion == expected


def test_post_hoc_outcome_is_rejected() -> None:
    plan_digest = "c" * 64
    document = evaluation_document(plan_digest, evaluated_at=NOW - timedelta(seconds=1))
    payload = MechanismEvaluationCreate(
        evaluation_key="DISC006-POSTHOC",
        plan_id=uuid4(),
        evaluation=document,
        evaluation_digest=record_digest(document),
        evaluated_by="reviewer",
    )
    with pytest.raises(FalsificationConflict, match="postdate"):
        register_evaluation(evaluation_db(document), payload)


def test_supporting_evidence_must_match_preregistered_test_set() -> None:
    plan_digest = "c" * 64
    document = evaluation_document(plan_digest)
    changed = document.model_copy(
        update={
            "outcomes": [
                document.outcomes[0].model_copy(update={"test_key": "post-hoc-test"})
            ]
        }
    )
    payload = MechanismEvaluationCreate(
        evaluation_key="DISC006-CHANGED",
        plan_id=uuid4(),
        evaluation=changed,
        evaluation_digest=record_digest(changed),
        evaluated_by="reviewer",
    )
    with pytest.raises(FalsificationConflict, match="preregistered"):
        register_evaluation(evaluation_db(changed), payload)


def test_routes_expose_plans_and_computed_evaluations() -> None:
    paths = {route.path for route in router.routes}
    assert "/v1/research/falsification/plans" in paths
    assert "/v1/research/falsification/evaluations" in paths
