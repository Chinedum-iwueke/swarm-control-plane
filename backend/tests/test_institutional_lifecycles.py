from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.schemas.institutional_lifecycle import InstitutionalTransitionCreate
from app.services.institutional_lifecycle import (
    INITIAL_STATES,
    TRANSITIONS,
    _verify_replay,
    next_state,
    validate_cross_dimension_guard,
    validate_expected_version,
)
from fastapi import HTTPException
from pydantic import ValidationError


def states(**updates: str) -> dict[str, str]:
    result = dict(INITIAL_STATES)
    result.update(updates)
    return result


def test_research_success_does_not_imply_other_lifecycles() -> None:
    current = states(research="succeeded")
    assert current["evidence"] == "unassessed"
    assert current["operations"] == "not-considered"
    assert current["capital"] == "no-authority"


def test_operations_require_both_research_and_evidence() -> None:
    with pytest.raises(HTTPException, match="succeeded research"):
        validate_cross_dimension_guard(
            "operations", "nominate", states(research="succeeded")
        )
    validate_cross_dimension_guard(
        "operations",
        "nominate",
        states(research="succeeded", evidence="admissible"),
    )


def test_capital_requires_live_operations_and_admissible_evidence() -> None:
    with pytest.raises(HTTPException, match="live operations"):
        validate_cross_dimension_guard(
            "capital",
            "qualify",
            states(research="succeeded", evidence="admissible", operations="demo"),
        )
    validate_cross_dimension_guard(
        "capital",
        "qualify",
        states(evidence="admissible", operations="live"),
    )


@pytest.mark.parametrize(
    ("dimension", "state", "command", "expected"),
    [
        ("research", "running", "succeed", "succeeded"),
        ("evidence", "unassessed", "invalidate", "invalid"),
        ("operations", "live", "suspend", "suspended"),
        ("capital", "allocated", "reduce", "reduced"),
    ],
)
def test_declared_transitions_are_dimension_specific(
    dimension: str, state: str, command: str, expected: str
) -> None:
    assert next_state(dimension, state, command) == expected


def test_invalid_transition_fails_closed() -> None:
    with pytest.raises(HTTPException) as error:
        next_state("capital", "no-authority", "allocate")
    assert error.value.detail["reason"] == "invalid-transition"


def test_every_declared_transition_and_no_undeclared_state_pair() -> None:
    for dimension, transitions in TRANSITIONS.items():
        for (prior, command), resulting in transitions.items():
            assert next_state(dimension, prior, command) == resulting
            assert prior != resulting


def test_stale_optimistic_version_fails_closed() -> None:
    with pytest.raises(HTTPException) as error:
        validate_expected_version(current_version=4, expected_version=3)
    assert error.value.detail == {"reason": "stale-version", "current_version": 4}
    validate_expected_version(current_version=4, expected_version=4)


def test_transition_clock_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        InstitutionalTransitionCreate.model_validate(
            {
                "command_id": uuid4(),
                "actor": "founder-operator",
                "dimension": "research",
                "command": "register",
                "expected_version": 0,
                "subject_digest": "a" * 64,
                "reason": "Register the bounded research lifecycle subject.",
                "risk_level": 1,
                "effective_at": "2026-08-25T12:00:00",
            }
        )


def test_replay_detects_projection_drift() -> None:
    projection = SimpleNamespace(
        dimension="research",
        state="succeeded",
        version=1,
        last_event_digest="event-1",
    )
    event = SimpleNamespace(
        dimension="research",
        prior_state="proposed",
        resulting_state="registered",
        expected_version=0,
        resulting_version=1,
        prior_event_digest=None,
        record_digest="event-1",
    )
    with pytest.raises(HTTPException, match="projection"):
        _verify_replay([projection], [event])


def test_replay_accepts_exact_event_chain() -> None:
    projection = SimpleNamespace(
        dimension="research",
        state="registered",
        version=1,
        last_event_digest="event-1",
    )
    event = SimpleNamespace(
        dimension="research",
        prior_state="proposed",
        resulting_state="registered",
        expected_version=0,
        resulting_version=1,
        prior_event_digest=None,
        record_digest="event-1",
    )
    _verify_replay([projection], [event])
