from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.offline_rl import router
from app.schemas.offline_rl import (
    OfflineRLDatasetCreate,
    OfflineRLDatasetSpecification,
)
from app.services.offline_rl import OfflineRLConflict, build_audit, register_dataset
from app.services.research import record_digest
from pydantic import ValidationError

BUILD_ID = uuid4()


def specification(**updates):
    reward_digest = record_digest({"reward": "net-return-1h"})
    value = {
        "schema_version": "offline-rl-dataset-contract-v1.0.0",
        "shadow_journal_digest": record_digest({"journal": "sealed"}),
        "shadow_replay_digest": record_digest({"replay": "exact"}),
        "shadow_journal_sealed": True,
        "shadow_capital_or_order_authority": False,
        "transition_schema_version": "offline-transition-v1",
        "episode_definition": "One UTC trading day ending at the final observed interval.",
        "behavior_policy": {
            "policy_key": "shadow-policy",
            "policy_version": "v1",
            "policy_digest": record_digest({"policy": "shadow-v1"}),
            "propensity_source": "logged",
            "minimum_allowed_propensity": 0.05,
            "deterministic": False,
        },
        "state_features": [
            {
                "feature_key": "lagged-return",
                "availability_lag_steps": 1,
                "source_digest": record_digest({"feature": "lagged-return"}),
            }
        ],
        "actions": [
            {
                "action_key": "flat",
                "kind": "discrete",
                "unit": "position",
                "lower_bound": -0.01,
                "upper_bound": 0.01,
            },
            {
                "action_key": "long",
                "kind": "continuous",
                "unit": "position",
                "lower_bound": 0.01,
                "upper_bound": 1.0,
            },
        ],
        "reward": {
            "reward_key": "net-return-1h",
            "formula": "next_hour_return - fees - slippage",
            "horizon_steps": 1,
            "availability_lag_steps": 1,
            "reward_digest": reward_digest,
            "independent_rebuild_digest": reward_digest,
            "clipping": "none",
        },
        "confounders": [
            {
                "confounder_key": "market-impact",
                "status": "proxy",
                "mitigation": "Retain capacity proxy and abstain outside observed support.",
            }
        ],
        "audit_summary": {
            "transition_count": 1000,
            "episode_count": 40,
            "action_support": [
                {
                    "action_key": "flat",
                    "observations": 500,
                    "minimum_propensity": 0.2,
                    "maximum_importance_weight": 5.0,
                },
                {
                    "action_key": "long",
                    "observations": 500,
                    "minimum_propensity": 0.1,
                    "maximum_importance_weight": 10.0,
                },
            ],
            "duplicate_transition_count": 0,
            "out_of_order_transition_count": 0,
            "state_availability_violation_count": 0,
            "reward_availability_violation_count": 0,
            "missing_propensity_count": 0,
            "terminal_transition_count": 40,
        },
        "evaluation": {
            "estimators": [
                "direct_method",
                "doubly_robust",
                "weighted_importance_sampling",
            ],
            "minimum_action_support": 50,
            "maximum_importance_weight": 20.0,
            "confidence_level": 0.95,
            "unsupported_action_policy": "abstain",
            "model_selection_dataset": "separate_from_evaluation",
            "action_authority": False,
            "capital_authority": False,
        },
    }
    value.update(updates)
    return value


def payload(spec=None):
    spec = spec or specification()
    validated = OfflineRLDatasetSpecification.model_validate(spec)
    return OfflineRLDatasetCreate.model_validate(
        {
            "contract_key": "RL001-PILOT",
            "dataset_build_id": BUILD_ID,
            "contract": validated,
            "contract_digest": record_digest(validated),
            "registered_by": "rl001-pilot",
        }
    )


def build():
    return SimpleNamespace(
        id=BUILD_ID,
        rows=1200,
        content_digest=record_digest({"content": "dataset"}),
        rebuild_content_digest=record_digest({"content": "dataset"}),
        record_digest=record_digest({"build": "DATA002"}),
        quality_results=[{"check": "missing_bar_count", "passed": True}],
    )


def test_qualified_contract_retains_limitations_and_no_authority():
    audit, status = build_audit(payload(), build())
    assert status == "qualified"
    assert audit["causal_availability_valid"] is True
    assert audit["limitations"][0]["confounder_key"] == "market-impact"
    assert audit["policy_improvement_authority"] is False
    assert audit["capital_authority"] is False


@pytest.mark.parametrize(
    ("field", "failure"),
    [
        ("state_availability_violation_count", "temporal_or_leakage_violation"),
        ("reward_availability_violation_count", "temporal_or_leakage_violation"),
        ("missing_propensity_count", "missing_behavior_propensity"),
    ],
)
def test_leakage_and_propensity_failures_quarantine(field, failure):
    spec = specification()
    spec["audit_summary"][field] = 1
    audit, status = build_audit(payload(spec), build())
    assert status == "quarantined"
    assert failure in audit["failures"]


def test_action_support_gap_quarantines():
    spec = specification()
    spec["audit_summary"]["action_support"][1]["observations"] = 10
    audit, status = build_audit(payload(spec), build())
    assert status == "quarantined"
    assert audit["support_failures"][0]["action_key"] == "long"


def test_policy_weight_mismatch_quarantines():
    spec = specification()
    spec["audit_summary"]["action_support"][1]["maximum_importance_weight"] = 25
    audit, status = build_audit(payload(spec), build())
    assert status == "quarantined"
    assert "importance_weight_exceeds_cap" in audit["support_failures"][0]["reasons"]


def test_reward_rebuild_mismatch_is_rejected_by_schema():
    spec = specification()
    spec["reward"]["independent_rebuild_digest"] = record_digest({"wrong": True})
    with pytest.raises(ValidationError, match="reward rebuild"):
        payload(spec)


def test_action_support_must_cover_action_space():
    spec = specification()
    spec["audit_summary"]["action_support"][1]["action_key"] = "flat"
    with pytest.raises(ValidationError, match="cover every action"):
        payload(spec)


def test_contract_digest_mismatch_is_rejected():
    item = payload().model_copy(update={"contract_digest": "0" * 64})
    with pytest.raises(OfflineRLConflict, match="digest"):
        build_audit(item, build())


def test_registration_requires_registered_data_build():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(OfflineRLConflict, match="DATA-002"):
        register_dataset(db, payload())


def test_routes_are_registered():
    paths = {route.path for route in router.routes}
    assert "/v1/research/offline-rl-datasets" in paths
    assert "/v1/research/offline-rl-datasets/{dataset_id}" in paths
