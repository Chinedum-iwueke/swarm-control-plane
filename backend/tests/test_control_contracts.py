import pytest
from app.schemas import ControlMutation, EffectiveControlResponse, TaskLeaseResponse
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
