from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.symbolic_search import router
from app.schemas.symbolic_search import SymbolicCandidateCreate, SymbolicSearchCreate
from app.services.research import record_digest
from app.services.symbolic_search import (
    SymbolicSearchConflict,
    quarantine_run,
    register_symbolic_search,
    validate_candidate,
)


def program():
    base_expression = {
        "op": "divide",
        "args": [
            {"op": "field", "args": ["close", 1]},
            {"op": "field", "args": ["close", 2]},
        ],
    }
    return SimpleNamespace(
        id=uuid4(),
        status="active",
        compiled_digest="a" * 64,
        source={
            "fields": {
                "close": {
                    "unit": "usd",
                    "domain": "positive",
                    "clock": "decision_close",
                    "availability_lag": 0,
                }
            },
            "parameters": {},
            "factors": {
                "base": {
                    "expression": base_expression,
                    "output_unit": "dimensionless",
                    "missing_policy": "reject",
                }
            },
        },
    )


def policy(tools=None):
    return SimpleNamespace(
        id=uuid4(),
        status="active",
        bundle_digest="b" * 64,
        policy={"output_authority": "data_only"},
        allowed_tools=tools or [],
    )


def run_request(**updates):
    value = {
        "run_key": "DISC005-SYMBOLIC-R1",
        "base_factor_program_id": uuid4(),
        "prompt_policy_bundle_id": uuid4(),
        "constraints": {
            "maximum_candidates": 4,
            "maximum_nodes": 12,
            "maximum_depth": 6,
            "maximum_constants": 1,
            "allowed_operators": ["field", "constant", "add", "multiply", "divide"],
            "required_fields": ["close"],
            "allow_parameters": False,
        },
        "generated_by": "symbolic-generator",
    }
    value.update(updates)
    return SymbolicSearchCreate.model_validate(value)


def expression():
    return {
        "op": "add",
        "args": [
            {
                "op": "divide",
                "args": [
                    {"op": "field", "args": ["close", 1]},
                    {"op": "field", "args": ["close", 2]},
                ],
            },
            {"op": "constant", "args": [0.01]},
        ],
    }


def candidate(key="candidate-1", expr=None, claimed=None, candidate_index=0):
    proposal = {
        "expression": expr or expression(),
        "output_unit": "dimensionless",
        "generator": {
            "provider": "openai",
            "model": "codex",
            "version": "2026-08",
            "seed": 7,
            "candidate_index": candidate_index,
        },
    }
    return SymbolicCandidateCreate.model_validate(
        {
            "candidate_key": key,
            **proposal,
            "output_digest": claimed or record_digest(proposal),
            "submitted_by": "symbolic-generator",
        }
    )


def active_run(**updates):
    value = {
        "id": uuid4(),
        "status": "active",
        "base_factor_program_id": uuid4(),
        "constraints_digest": "c" * 64,
        "constraints": run_request().constraints.model_dump(mode="json"),
        "candidate_count": 0,
        "accepted_count": 0,
        "closure": {},
    }
    value.update(updates)
    return SimpleNamespace(**value)


def validation_db(run=None, prior=None, base=None):
    db = MagicMock()
    db.scalar.return_value = run or active_run()
    db.scalars.return_value.all.return_value = prior or []
    db.get.return_value = base or program()
    return db


def test_run_requires_active_data_only_toolless_policy():
    db = MagicMock()
    db.get.side_effect = [program(), policy(["shell"])]
    with pytest.raises(SymbolicSearchConflict, match="unsafe tools"):
        register_symbolic_search(db, run_request())


def test_read_only_research_retrieval_policy_is_allowed():
    db = MagicMock()
    db.get.side_effect = [program(), policy(["research.retrieve"])]
    db.scalar.return_value = None
    record = register_symbolic_search(db, run_request())
    assert record.constraints["prompt_policy_digest"] == "b" * 64


def test_run_rejects_unknown_required_field():
    db = MagicMock()
    db.get.side_effect = [program(), policy()]
    request = run_request(
        constraints={
            **run_request().constraints.model_dump(),
            "required_fields": ["future_price"],
        }
    )
    with pytest.raises(SymbolicSearchConflict, match="absent"):
        register_symbolic_search(db, request)


def test_valid_candidate_is_compiled_without_authority():
    record = validate_candidate(validation_db(), active_run().id, candidate())
    assert record.status == "accepted"
    assert record.compiled["action_authority"] is False
    assert record.compiled["nodes"] <= 12


def test_generator_digest_drift_is_retained_as_rejection():
    record = validate_candidate(
        validation_db(), active_run().id, candidate(claimed="f" * 64)
    )
    assert record.status == "rejected"
    assert "generator_output_digest_mismatch" in record.violations


def test_same_generator_index_cannot_emit_different_programs():
    run = active_run()
    db = validation_db(run=run)
    first = validate_candidate(db, run.id, candidate())
    db.scalars.return_value.all.return_value = [first]
    changed = {"op": "field", "args": ["close", 1]}
    second = validate_candidate(db, run.id, candidate("candidate-2", changed))
    assert "nondeterministic_generator_output" in second.violations


def test_arbitrary_program_operator_is_never_executed():
    hostile = {"op": "python_eval", "args": ["__import__('os').system('id')"]}
    record = validate_candidate(
        validation_db(), active_run().id, candidate(expr=hostile)
    )
    assert record.status == "rejected"
    assert any("disallowed_operators" in item for item in record.violations)


def test_current_bar_leakage_is_rejected_by_disc003_compiler():
    unsafe = {"op": "field", "args": ["close", 0]}
    record = validate_candidate(
        validation_db(), active_run().id, candidate(expr=unsafe)
    )
    assert record.status == "rejected"
    assert any("causally available" in item for item in record.violations)


def test_complexity_budget_fails_closed():
    constrained = active_run()
    constrained.constraints["maximum_nodes"] = 2
    record = validate_candidate(
        validation_db(run=constrained), constrained.id, candidate()
    )
    assert "maximum_nodes_exceeded" in record.violations


def test_commutative_reordering_is_semantic_duplicate():
    run = active_run()
    db = validation_db(run=run)
    first = validate_candidate(db, run.id, candidate())
    reordered = expression()
    reordered["args"].reverse()
    db.scalars.return_value.all.return_value = [first]
    second = validate_candidate(
        db, run.id, candidate("candidate-2", reordered, candidate_index=1)
    )
    assert second.status == "duplicate"
    assert second.semantic_digest == first.semantic_digest


def test_base_factor_is_semantic_duplicate():
    base = program()
    base_expression = base.source["factors"]["base"]["expression"]
    record = validate_candidate(
        validation_db(base=base), active_run().id, candidate(expr=base_expression)
    )
    assert record.status == "duplicate"


def test_candidate_budget_is_terminal():
    run = active_run(candidate_count=4)
    prior = [
        SimpleNamespace(
            proposal_digest=str(index) * 64,
            candidate_key=f"old-{index}",
            status="rejected",
            semantic_digest=None,
        )
        for index in range(1, 5)
    ]
    with pytest.raises(SymbolicSearchConflict, match="exhausted"):
        validate_candidate(validation_db(run=run, prior=prior), run.id, candidate())
    assert run.status == "complete"


def test_quarantine_is_terminal_and_retains_lineage():
    run = active_run(candidate_count=2, accepted_count=1)
    db = MagicMock()
    db.scalar.return_value = run
    result = quarantine_run(
        db,
        run.id,
        "security-reviewer",
        "Generator violated its deterministic contract.",
    )
    assert result.status == "quarantined"
    assert result.closure["lineage_retained"] is True
    assert result.closure["action_authority"] is False


def test_route_surface_is_registered():
    paths = {route.path for route in router.routes}
    assert "/v1/research/symbolic-searches/{run_id}/candidates" in paths
    assert "/v1/research/symbolic-searches/{run_id}/quarantine" in paths
