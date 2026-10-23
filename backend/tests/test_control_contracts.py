from types import SimpleNamespace

import pytest

from app.schemas import ControlMutation, EffectiveControlResponse, TaskLeaseResponse
from app.services.controls import task_matches_control_scope
from pydantic import ValidationError


def test_control_mutation_is_strictly_typed() -> None:
    mutation = ControlMutation(
        scope_type="machine",
        scope_key="vm1-developer",
        reason="Maintenance",
        actor="founder-operator",
    )
    assert mutation.scope_type == "machine"

    with pytest.raises(ValidationError):
        ControlMutation(
            scope_type="project",
            scope_key="swarm-control-plane",
            reason="Maintenance",
            actor="founder-operator",
        )


def test_paused_lease_and_effective_control_contracts() -> None:
    lease = TaskLeaseResponse(
        task=None,
        lease_token=None,
        paused=True,
        pause_reasons=["maintenance"],
    )
    control = EffectiveControlResponse(paused=True, reasons=["maintenance"])

    assert lease.paused is True
    assert control.reasons == lease.pause_reasons


def test_autonomous_research_scope_blocks_loop_work_not_founder_conversation() -> None:
    scope = SimpleNamespace(
        scope_type="workflow", scope_key="autonomous-research"
    )
    founder_turn = SimpleNamespace(
        task_type="founder_request",
        project="bulletproof_bt",
        created_by="founder:primary",
    )
    alpha_test = SimpleNamespace(
        task_type="alpha_research_execution",
        project="bulletproof_bt",
        created_by="alpha-campaign-director",
    )
    strategy_engineering = SimpleNamespace(
        task_type="engineering_mission",
        project="bulletproof_bt",
        created_by="alpha-campaign-director",
    )

    assert task_matches_control_scope(scope, founder_turn) is False
    assert task_matches_control_scope(scope, alpha_test) is True
    assert task_matches_control_scope(scope, strategy_engineering) is True
