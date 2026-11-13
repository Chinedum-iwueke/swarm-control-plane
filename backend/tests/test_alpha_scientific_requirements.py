from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.alpha_discovery import (
    AlphaScientificRequirements,
    AlphaRepresentationPlan,
)
from app.services.alpha_discovery import _apply_representation_plans


def requirements():
    return {
        "research_bar_minutes": 20,
        "feature_warmup_bars": 144,
        "minimum_training_bars": 5000,
        "minimum_validation_bars": 1000,
        "minimum_test_bars": 1000,
        "target_horizon_bars": 4,
        "purge_bars": 4,
        "embargo_bars": 2,
        "minimum_scientific_window_days": 365,
        "smoke_bars": 288,
        "minimum_event_support": {"signal_events": 40},
        "rationale": "Keep scientific support independent of the short runner smoke test.",
    }


def test_scientific_requirement_proposal_is_explicit_and_does_not_issue_receipts():
    value = requirements()
    before = deepcopy(value)
    assert AlphaScientificRequirements.model_validate(value).model_dump() == before
    for field in ("basis_digest", "coverage", "approved", "execution_authority"):
        with pytest.raises(ValidationError):
            AlphaScientificRequirements.model_validate(value | {field: True})


@pytest.mark.parametrize(
    "field,value",
    [
        ("minimum_training_bars", True),
        ("minimum_test_bars", 0),
        ("minimum_scientific_window_days", 31),
        ("minimum_event_support", {"signal_events": True}),
        ("minimum_event_support", {"signal_events": 0}),
    ],
)
def test_support_cannot_be_weakened_or_coerced(field, value):
    with pytest.raises(ValidationError):
        AlphaScientificRequirements.model_validate(requirements() | {field: value})


def plan():
    return {
        "schema_version": "adaptive-representation-plan-v1.0.0",
        "candidate_key": "test",
        "venue": "bybit",
        "instrument": "BTCUSDT",
        "instruments": ["BTCUSDT"],
        "basket_members": [
            {
                "instrument": "BTCUSDT",
                "role": "primary",
                "legacy_groups": [],
                "selection_rationale": "Frozen target from the original research question.",
            }
        ],
        "source_timeframe": "1m",
        "research_timeframe": "20m",
        "resampling_policy": "left_closed_left_labeled_complete_bars",
        "required_fields": ["close"],
        "minimum_history_observations": 525600,
        "liquidity_floor_usd": 0,
        "transformations": [
            {
                "output_field": "price",
                "operation": "identity",
                "input_fields": ["BTCUSDT__close"],
                "parameters": {},
                "fit_policy": "stateless",
                "rationale": "Only test the schema and immutable handoff in this fixture.",
            }
        ],
        "transformation_rationale": "Frozen point-in-time representation for schema validation.",
        "rejected_alternatives": ["No target-based selection"],
        "selection_data_boundary": "metadata_predictors_only_no_targets",
        "outcome_data_consulted": False,
        "scientific_requirements": requirements(),
    }


def test_source_history_is_not_training_research_bars_and_proposal_survives():
    value = plan()
    parsed = AlphaRepresentationPlan.model_validate(value)
    assert parsed.minimum_history_observations == 525600
    assert parsed.scientific_requirements.minimum_training_bars == 5000
    represented, _ = _apply_representation_plans(
        [{"candidate_key": "test", "question": "unchanged"}], [value]
    )
    assert represented[0]["scientific_requirements"] == requirements()
    assert "scientific_requirements" not in represented[0]["representation_plan"]
    assert represented[0]["question"] == "unchanged"


@pytest.mark.parametrize(
    "field,value", [("research_bar_minutes", 15), ("smoke_bars", 5000)]
)
def test_representation_rejects_clock_mismatch_and_oversized_smoke(field, value):
    document = plan()
    document["scientific_requirements"][field] = value
    with pytest.raises(ValidationError):
        AlphaRepresentationPlan.model_validate(document)
