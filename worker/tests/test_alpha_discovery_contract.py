from pathlib import Path
from types import SimpleNamespace

import pytest

from swarm_worker.executors.alpha_discovery import (
    AlphaDiscoveryError,
    AlphaDiscoveryExecutor,
    _prompt,
    _runtime_options,
    _schema,
)
from swarm_worker.policy import AlphaDiscoveryContract, validate_task_policy
from swarm_worker.workflows import WorkflowLoader


def test_discovery_domain_identifiers_match_canonical_intake():
    import re

    properties = _schema("hypothesis")["properties"]["candidates"]["items"][
        "properties"
    ]
    for key in ("domain_key", "cluster_key"):
        field = properties[key]
        assert re.fullmatch(field["pattern"], "perpetual-return-predictability")
        assert not re.fullmatch(field["pattern"], "perpetual_return_predictability")
        assert field["maxLength"] == 100


def test_discovery_runtime_is_private_and_separate_from_credentials(tmp_path):
    options = _runtime_options(tmp_path)
    runtime = tmp_path / "codex-runtime"
    assert runtime.stat().st_mode & 0o777 == 0o700
    assert options == (
        "-c",
        f'sqlite_home="{runtime}"',
        "-c",
        f'log_dir="{runtime / "logs"}"',
    )


def test_discovery_runtime_rejects_symlink(tmp_path):
    (tmp_path / "codex-runtime").symlink_to(tmp_path)
    with pytest.raises(AlphaDiscoveryError, match="symbolic link"):
        _runtime_options(tmp_path)


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


def test_discovery_prompt_separates_catalog_visibility_from_execution_scope():
    document = alpha_discovery_contract()
    document["context"]["lake_catalog"] = {
        "receipt_digest": "b" * 64,
        "assets": [["perp", "binance", "ETHUSDT"]],
        "execution_authority": False,
    }
    prompt = _prompt(AlphaDiscoveryContract.model_validate(document))
    assert "ETHUSDT" in prompt
    assert "physical inventory, not execution permission" in prompt
    assert "hypothesis-specific cross-group baskets" in prompt
    assert "one-year catalog candidate may be proposed" in prompt
    assert "only datasets listed as admitted may enter execution" in prompt


def test_hypothesis_schema_requires_pre_outcome_basket_and_safe_resampling():
    data = _schema("hypothesis")["properties"]["candidates"]["items"]["properties"][
        "data"
    ]
    assert {"instruments", "research_timeframe", "resampling_policy"}.issubset(
        data["required"]
    )
    properties = data["properties"]
    assert properties["timeframe"]["enum"] == ["1m"]
    assert properties["instruments"]["maxItems"] == 20
    assert properties["resampling_policy"]["enum"] == [
        "right_closed_left_labeled_complete_bars"
    ]


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
