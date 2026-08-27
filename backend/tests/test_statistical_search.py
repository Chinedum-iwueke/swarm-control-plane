from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.statistical_search import router
from app.schemas.statistical_search import SearchObservation, StatisticalSearchCreate
from app.services.statistical_search import (
    StatisticalSearchConflict,
    _rank,
    register_campaign,
    verify_event_chain,
)
from pydantic import ValidationError


def trials():
    result = []
    for ordinal, (x, y) in enumerate(((1, 10), (1, 20), (2, 10), (2, 20)), start=1):
        result.append(
            {
                "ordinal": ordinal,
                "parameters": {"x": x, "y": y},
                "trial_digest": f"{ordinal:064x}",
            }
        )
    return result


def request(method="random", maximum_evaluations=3, **updates):
    value = {
        "campaign_key": f"DISC004-{method.upper()}-R1",
        "factor_program_id": uuid4(),
        "method": method,
        "seed": 20260827,
        "objective": {"metric": "sharpe", "direction": "maximize"},
        "budget": {
            "maximum_evaluations": maximum_evaluations,
            "maximum_batches": 3,
            "batch_size": 1,
        },
        "exploration_weight": 1.0,
        "registered_by": "disc004-pilot",
    }
    value.update(updates)
    return StatisticalSearchCreate.model_validate(value)


def campaign(method, direction="maximize"):
    return SimpleNamespace(
        method=method,
        specification={
            "seed": 7,
            "objective": {"direction": direction},
            "exploration_weight": 0.5,
        },
    )


def test_random_ranking_is_seeded_and_deterministic():
    assert _rank(campaign("random"), trials(), {}) == _rank(
        campaign("random"), trials(), {}
    )


@pytest.mark.parametrize(
    "method", ["exhaustive", "structured", "random", "bayesian", "evolutionary"]
)
def test_every_method_returns_complete_unique_ranking(method):
    observed = {
        trials()[0]["trial_digest"]: {"status": "completed", "objective_value": 1.0}
    }
    ranked = _rank(campaign(method), trials()[1:], observed, trials())
    assert len(ranked) == 3
    assert len({item["trial_digest"] for item in ranked}) == 3


def test_bayesian_direction_changes_preference():
    universe = [
        {
            "ordinal": index,
            "parameters": {"x": index},
            "trial_digest": f"{index:064x}",
        }
        for index in range(1, 5)
    ]
    observed = {
        universe[0]["trial_digest"]: {"status": "completed", "objective_value": 10.0},
        universe[-1]["trial_digest"]: {"status": "completed", "objective_value": -10.0},
    }
    remaining = universe[1:3]
    maximum = _rank(campaign("bayesian", "maximize"), remaining, observed, universe)
    minimum = _rank(campaign("bayesian", "minimize"), remaining, observed, universe)
    assert maximum[0]["trial_digest"] != minimum[0]["trial_digest"]


def test_non_result_cannot_smuggle_objective_value():
    with pytest.raises(ValidationError, match="non-result"):
        SearchObservation.model_validate(
            {
                "trial_digest": "a" * 64,
                "status": "failed",
                "objective_value": 9.0,
                "result_digest": "b" * 64,
            }
        )


def test_completed_result_requires_objective_value():
    with pytest.raises(ValidationError, match="requires"):
        SearchObservation.model_validate(
            {"trial_digest": "a" * 64, "status": "completed", "result_digest": "b" * 64}
        )


def test_non_finite_objective_is_rejected():
    with pytest.raises(ValidationError):
        SearchObservation.model_validate(
            {
                "trial_digest": "a" * 64,
                "status": "completed",
                "objective_value": float("nan"),
                "result_digest": "b" * 64,
            }
        )


def test_event_chain_detects_tampering():
    event = SimpleNamespace(
        sequence=1,
        event_type="registered",
        detail={"action_authority": False},
        prior_digest="0" * 64,
        record_digest="f" * 64,
    )
    record = SimpleNamespace(id=uuid4(), event_head_digest="f" * 64)
    assert verify_event_chain(record, [event]) is False


def test_campaign_budget_cannot_exceed_compiled_universe():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=uuid4(),
        status="active",
        compiled={"trials": trials()},
        compiled_digest="c" * 64,
    )
    with pytest.raises(StatisticalSearchConflict, match="exceeds"):
        register_campaign(
            db,
            request(
                maximum_evaluations=5,
                budget={
                    "maximum_evaluations": 5,
                    "maximum_batches": 5,
                    "batch_size": 1,
                },
            ),
        )


def test_exhaustive_search_must_cover_entire_universe():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=uuid4(),
        status="active",
        compiled={"trials": trials()},
        compiled_digest="c" * 64,
    )
    with pytest.raises(StatisticalSearchConflict, match="complete universe"):
        register_campaign(db, request("exhaustive", 3))


def test_registration_retains_no_action_authority():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=uuid4(),
        status="active",
        compiled={"trials": trials()},
        compiled_digest="c" * 64,
    )
    db.scalars.return_value.all.return_value = []
    db.scalar.return_value = None
    record = register_campaign(db, request())
    event = db.add.call_args_list[-1].args[0]
    assert record.specification["budget"]["maximum_evaluations"] == 3
    assert event.detail["action_authority"] is False


def test_identical_registration_is_idempotent():
    existing = SimpleNamespace(specification_digest="placeholder")
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=uuid4(),
        status="active",
        compiled={"trials": trials()},
        compiled_digest="c" * 64,
    )
    payload = request()
    db.scalar.side_effect = [None]
    first = register_campaign(db, payload)
    existing.specification_digest = first.specification_digest
    db.scalar.side_effect = [existing]
    assert register_campaign(db, payload) is existing


def test_route_surface_is_registered():
    paths = {route.path for route in router.routes}
    assert "/v1/research/statistical-searches/{campaign_id}/proposals" in paths
    assert "/v1/research/statistical-searches/{campaign_id}/observations" in paths
    assert "/v1/research/statistical-searches/{campaign_id}/events" in paths
