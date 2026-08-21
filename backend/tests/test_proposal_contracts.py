from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas import FounderProposalDocument
from app.services.proposals import materialize_proposal, proposal_digest


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
        }
    )
    document = FounderProposalDocument.model_validate(payload)
    assert document.proposed_task.task_type == "research_memory_sync"
    assert set(document.proposed_task.input_contract.model_dump()) == {
        "repository",
        "workflow",
        "base_ref",
    }


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
