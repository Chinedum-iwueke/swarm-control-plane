from pathlib import Path

from swarm_worker.policy import AlphaDiscoveryContract
from swarm_worker.workflows import WorkflowLoader


def test_alpha_discovery_contract_and_fixed_workflow():
    contract = AlphaDiscoveryContract.model_validate(
        {
            "repository": "swarm-control-plane",
            "workflow": "alpha-discovery",
            "base_ref": "main",
            "stage": "intelligence",
            "mandate_id": "11111111-1111-1111-1111-111111111111",
            "mandate_digest": "a" * 64,
            "cycle_id": "22222222-2222-2222-2222-222222222222",
            "maximum_candidates": 5,
            "context": {"research_intelligence": {"citations": []}},
            "authority": "no_capital_research",
        }
    )
    workflow = WorkflowLoader(Path("worker/workflows")).load(contract.workflow)
    assert workflow.task_type == "alpha_discovery"
    assert workflow.steps == []
