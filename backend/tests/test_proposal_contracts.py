from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from app.schemas import FounderProposalDocument, FounderProposalResponse
from app.services.proposals import _task_create, materialize_proposal, proposal_digest
from pydantic import ValidationError


def valid_document() -> dict:
    return {
        "schema_version": 1,
        "summary": "Create a bounded code validation task.",
        "interpretation": "Validate the named repository at its approved base ref.",
        "recommended_action": "create_task",
        "assumptions": [],
        "clarification_questions": [],
        "target_role": "Restricted VM1 engineering worker",
        "target_role_reason": "The role can run named validation workflows.",
        "safety_constraints": ["No primary checkout writes."],
        "proposed_task": {
            "project": "swarm-control-plane",
            "task_type": "code_validation",
            "title": "Validate swarm control plane",
            "objective": "Compile and test an isolated swarm-control-plane worktree.",
            "priority": 50,
            "risk_level": 1,
            "input_contract": {
                "repository": "swarm-control-plane",
                "workflow": "code-validation",
                "base_ref": "main",
            },
            "expected_outputs": ["validation logs"],
            "acceptance_criteria": ["Compilation and tests pass."],
            "approval_policy": {"kind": "automatic", "risk": 1},
            "approval_required": False,
            "required_capabilities": ["git", "python", "testing"],
            "allowed_machines": ["vm1-developer"],
            "max_attempts": 1,
        },
    }


def test_proposal_is_strict_digest_bound_and_non_executable() -> None:
    document = FounderProposalDocument.model_validate(valid_document())
    assert len(proposal_digest(document)) == 64
    unsafe = valid_document()
    unsafe["proposed_task"]["input_contract"]["command"] = ["pytest"]
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(unsafe)
    unknown = valid_document()
    unknown["execute_now"] = True
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(unknown)


def test_non_task_recommendations_cannot_smuggle_a_task() -> None:
    payload = valid_document()
    payload["recommended_action"] = "needs_clarification"
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(payload)


def test_proposal_rejects_invented_worker_route() -> None:
    payload = valid_document()
    payload["proposed_task"]["required_capabilities"] = ["compile"]
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(payload)


def test_memory_sync_proposal_has_no_path_or_command_surface() -> None:
    payload = valid_document()
    payload["proposed_task"].update(
        {
            "project": "bulletproof_bt",
            "task_type": "research_memory_sync",
            "input_contract": {
                "repository": "bulletproof_bt",
                "workflow": "research-memory-sync",
                "base_ref": "main",
            },
            "risk_level": 0,
            "approval_policy": {"kind": "automatic", "risk": 0},
            "required_capabilities": ["git", "python", "research-memory-sync"],
        }
    )
    document = FounderProposalDocument.model_validate(payload)
    assert document.proposed_task.task_type == "research_memory_sync"
    assert set(document.proposed_task.input_contract.model_dump()) == {
        "repository",
        "workflow",
        "base_ref",
    }


def test_founder_hypothesis_intake_is_bounded_before_execution() -> None:
    payload = valid_document()
    payload["proposed_task"].update(
        {
            "task_type": "founder_hypothesis_intake",
            "title": "Challenge founder funding hypothesis",
            "objective": "Queue the idea for independent evidence and predictive review.",
            "input_contract": {
                "repository": "swarm-control-plane",
                "workflow": "founder-hypothesis-intake",
                "base_ref": "main",
                "mandate_id": "11111111-1111-4111-8111-111111111111",
                "mandate_digest": "a" * 64,
                "research_idea": "Test whether elevated funding predicts subsequent perpetual returns.",
                "minimum_history_days": 365,
                "maximum_variants": 8,
                "universe_selection_policy": "preregistered_point_in_time",
                "universe_slices": ["stable", "volatile"],
            },
            "risk_level": 0,
            "approval_policy": {"kind": "explicit", "risk": 0},
            "required_capabilities": [
                "research-intelligence",
                "research-proposal",
                "prior-art",
            ],
            "allowed_machines": ["vm1-developer"],
        }
    )
    document = FounderProposalDocument.model_validate(payload)
    assert document.proposed_task.input_contract.maximum_variants == 8
    payload["proposed_task"]["input_contract"]["minimum_history_days"] = 30
    with pytest.raises(ValidationError):
        FounderProposalDocument.model_validate(payload)


def test_materialization_is_exactly_once() -> None:
    proposal = SimpleNamespace(
        status="materialized",
        proposal=valid_document(),
        source_task_id=UUID("11111111-1111-4111-8111-111111111111"),
    )
    with pytest.raises(Exception) as raised:
        materialize_proposal(
            SimpleNamespace(),
            proposal,
            actor="founder",
            reason="Already reviewed and created.",
            now=datetime.now(UTC),
        )
    assert getattr(raised.value, "status_code", None) == 409


def test_infrastructure_materialization_removes_null_parameter_scaffolding() -> None:
    payload = valid_document()
    payload["proposed_task"].update(
        {
            "project": "swarm-control-plane",
            "task_type": "infrastructure_observation",
            "input_contract": {
                "runbook": "vm2-infrastructure",
                "runbook_version": "1.0.0",
                "operation": "observe-control-plane",
                "target": "vm2-control-plane",
                "parameters": {
                    "service": None,
                    "certificate_profile": None,
                },
                "package_name": None,
                "package_version": None,
                "package_digest": None,
            },
            "risk_level": 0,
            "approval_policy": {"kind": "automatic", "risk": 0},
            "required_capabilities": [
                "infrastructure-observation",
                "service-health",
                "controlled-restart",
            ],
            "allowed_machines": ["vm2-deployment"],
        }
    )
    document = FounderProposalDocument.model_validate(payload)
    source = SimpleNamespace(id=UUID("11111111-1111-4111-8111-111111111111"))

    task = _task_create(
        document.proposed_task,
        source,
        "founder",
        datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert task.input_contract == {
        "runbook": "vm2-infrastructure",
        "runbook_version": "1.0.0",
        "operation": "observe-control-plane",
        "target": "vm2-control-plane",
        "parameters": {},
    }


def test_historical_proposal_response_remains_readable() -> None:
    now = datetime.now(UTC)
    response = FounderProposalResponse.model_validate(
        {
            "id": UUID("11111111-1111-4111-8111-111111111111"),
            "source_task_id": UUID("22222222-2222-4222-8222-222222222222"),
            "planner_agent_id": UUID("33333333-3333-4333-8333-333333333333"),
            "status": "proposed",
            "proposal": {"legacy_schema": True},
            "proposal_digest": "a" * 64,
            "decision_reason": None,
            "decided_by": None,
            "materialized_task_id": None,
            "created_at": now,
            "updated_at": now,
            "decided_at": None,
        }
    )
    assert response.proposal == {"legacy_schema": True}
