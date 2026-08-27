from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.factor_language import router
from app.schemas.factor_language import FactorProgramCreate
from app.services.factor_language import (
    FactorLanguageConflict,
    compile_program,
    register_factor_program,
)

HYPOTHESIS_ID = uuid4()


def source(**updates):
    value = {
        "schema_version": "factor-experiment-language-v1.0.0",
        "representation_contract_digest": "a" * 64,
        "dataset_manifest_digest": "b" * 64,
        "decision_clock": "decision_close",
        "fields": {
            "close": {
                "unit": "usd",
                "domain": "positive",
                "clock": "decision_close",
                "availability_lag": 0,
            },
            "volume": {
                "unit": "contracts",
                "domain": "nonnegative",
                "clock": "decision_close",
                "availability_lag": 1,
            },
        },
        "parameters": {"lookback": [2, 4], "threshold": [0.0, 0.01]},
        "factors": {
            "lagged_return": {
                "expression": {
                    "op": "subtract",
                    "args": [
                        {
                            "op": "divide",
                            "args": [
                                {"op": "field", "args": ["close", 1]},
                                {"op": "field", "args": ["close", 2]},
                            ],
                        },
                        {"op": "constant", "args": [1]},
                    ],
                },
                "output_unit": "dimensionless",
                "missing_policy": "reject",
            }
        },
        "label": {"field": "close", "horizon": 1, "kind": "forward_return"},
        "maximum_trials": 4,
    }
    value.update(updates)
    return value


def payload(**source_updates):
    return FactorProgramCreate.model_validate(
        {
            "program_key": "DISC003-LAGGED-MOMENTUM-R1",
            "hypothesis_id": HYPOTHESIS_ID,
            "source": source(**source_updates),
            "registered_by": "factor-language-pilot",
        }
    )


def test_compilation_is_deterministic_and_finite() -> None:
    first = compile_program(payload())
    second = compile_program(payload())
    assert first == second
    assert first[0]["trial_count"] == 4
    assert len({trial["trial_digest"] for trial in first[0]["trials"]}) == 4
    assert first[0]["action_authority"] is False


def test_same_program_key_does_not_enter_semantic_digest() -> None:
    first = payload()
    second = first.model_copy(update={"program_key": "DISC003-ALIAS-R1"})
    assert compile_program(first)[2] == compile_program(second)[2]


def test_current_bar_feature_is_rejected_as_future_leakage() -> None:
    request = source()
    request["factors"]["lagged_return"]["expression"] = {
        "op": "field",
        "args": ["close", 0],
    }
    with pytest.raises(FactorLanguageConflict, match="causally available"):
        compile_program(payload(**request))


def test_unknown_operator_is_rejected() -> None:
    request = source()
    request["factors"]["lagged_return"]["expression"] = {
        "op": "python_eval",
        "args": ["__import__('os')"],
    }
    with pytest.raises(FactorLanguageConflict, match="unsupported operator"):
        compile_program(payload(**request))


def test_unit_mismatch_is_rejected() -> None:
    request = source()
    request["factors"]["lagged_return"]["expression"] = {
        "op": "add",
        "args": [
            {"op": "field", "args": ["close", 1]},
            {"op": "field", "args": ["volume", 0]},
        ],
    }
    request["factors"]["lagged_return"]["output_unit"] = "usd"
    with pytest.raises(FactorLanguageConflict, match="identical units"):
        compile_program(payload(**request))


def test_grid_cannot_exceed_registered_budget() -> None:
    with pytest.raises(FactorLanguageConflict, match="maximum_trials"):
        compile_program(payload(maximum_trials=3))


def test_registration_requires_hypothesis() -> None:
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(FactorLanguageConflict, match="registered hypothesis"):
        register_factor_program(db, payload())


def test_route_surface_is_registered() -> None:
    paths = {route.path for route in router.routes}
    assert paths == {
        "/v1/research/factor-programs",
        "/v1/research/factor-programs/{program_id}",
    }
