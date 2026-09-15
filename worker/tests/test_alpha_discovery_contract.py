from pathlib import Path
from types import SimpleNamespace

from swarm_worker.executors.alpha_discovery import AlphaDiscoveryExecutor
from swarm_worker.policy import AlphaDiscoveryContract, validate_task_policy
from swarm_worker.workflows import WorkflowLoader


def test_discovery_subprocess_keeps_fixed_jitless_sandbox_environment(monkeypatch):
    monkeypatch.setenv("NODE_OPTIONS", "--require=/untrusted.js")
    monkeypatch.setenv("SWARM_AGENT_TOKEN", "must-not-leak")
    executor = AlphaDiscoveryExecutor(
        codex_home=Path("/safe/codex"),
        codex_model="test",
        timeout_seconds=60,
        heartbeat_interval_seconds=5,
    )
    workspace = SimpleNamespace(
        plan=SimpleNamespace(attempt_directory=Path("/safe/attempt"))
    )
    env = executor._environment(workspace)
    assert env["NODE_OPTIONS"] == "--jitless"
    assert env["HOME"] == "/safe/attempt"
    assert env["CODEX_HOME"] == "/safe/codex"
    assert "SWARM_AGENT_TOKEN" not in env


def alpha_discovery_contract() -> dict:
    return {
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


def test_alpha_discovery_contract_and_fixed_workflow():
    contract = AlphaDiscoveryContract.model_validate(alpha_discovery_contract())
    workflow = WorkflowLoader(Path("worker/workflows")).load(contract.workflow)
    assert workflow.task_type == "alpha_discovery"
    assert workflow.steps == []


def test_alpha_discovery_contract_survives_complete_policy_validation():
    task = SimpleNamespace(
        task_type="alpha_discovery",
        input_contract=alpha_discovery_contract(),
        allowed_machines=["vm1-developer"],
        required_capabilities=["research-intelligence", "knowledge-retrieval"],
        risk_level=0,
    )
    identity = SimpleNamespace(
        capabilities=["research-intelligence", "knowledge-retrieval"],
        risk_ceiling=0,
    )

    validated = validate_task_policy(
        task,
        identity,
        WorkflowLoader(Path("worker/workflows")),
        worker_machine="vm1-developer",
    )

    assert isinstance(validated.contract, AlphaDiscoveryContract)
