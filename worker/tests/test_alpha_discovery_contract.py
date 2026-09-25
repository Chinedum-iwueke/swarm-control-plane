from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from swarm_worker.executors.alpha_discovery import (
    AlphaDiscoveryError,
    AlphaDiscoveryExecutor,
    _normalize_output,
    _prompt,
    _runtime_options,
    _schema,
)
from swarm_worker.models import WorkflowExecutionResult
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


def test_hypothesis_schema_enforces_api_candidate_bounds():
    properties = _schema("hypothesis")["properties"]["candidates"]["items"][
        "properties"
    ]

    assert properties["horizon"] == {
        "type": "string",
        "minLength": 2,
        "maxLength": 100,
    }
    assert properties["question"]["maxLength"] == 2000
    assert properties["mechanism"]["maxLength"] == 4000
    assert (
        properties["parameter_budget"]["properties"]["maximum_variants"]["maximum"] == 8
    )
    assert (
        properties["data"]["properties"]["minimum_history_observations"]["minimum"]
        == 500
    )
    assert properties["evidence_object_ids"]["maxItems"] == 20
    assert "{8}-" in properties["evidence_object_ids"]["items"]["pattern"]
    assert properties["evidence_digests"]["items"]["pattern"] == "^[0-9a-f]{64}$"
    assert properties["expected_information_gain"]["maximum"] == 1


def test_intelligence_and_equation_evidence_identifiers_are_typed():
    intelligence_pair = _schema("intelligence")["properties"]["research_brief"][
        "properties"
    ]["evidence_pairs"]["items"]["properties"]
    hypothesis = _schema("hypothesis")["properties"]["candidates"]["items"][
        "properties"
    ]
    equation = hypothesis["equations"]["items"]["properties"]

    assert "{8}-" in intelligence_pair["object_id"]["pattern"]
    assert intelligence_pair["content_digest"]["pattern"] == "^[0-9a-f]{64}$"
    assert equation["source_object_id"] == intelligence_pair["object_id"]
    assert equation["source_content_digest"] == intelligence_pair["content_digest"]


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


def test_alpha_data_admission_fixed_workflow_is_allowlisted():
    workflow = WorkflowLoader(Path("worker/workflows")).load(
        "alpha-data-admission"
    )

    assert workflow.task_type == "alpha_data_admission"
    assert workflow.steps == []


def test_alpha_data_admission_has_bounded_multi_receipt_envelope():
    common = {
        "repository": "bulletproof_bt",
        "base_commit": "a" * 40,
        "task_attempt": 1,
        "total_duration_seconds": 1,
        "steps": [],
        "success": True,
    }

    admitted = WorkflowExecutionResult(
        workflow="alpha-data-admission",
        summary={"alpha_data_admission": {"receipts": ["x" * 9_000] * 8}},
        **common,
    )
    assert len(admitted.summary["alpha_data_admission"]["receipts"]) == 8

    with pytest.raises(ValidationError, match="16 KiB"):
        WorkflowExecutionResult(
            workflow="engineering-mission",
            summary={"payload": "x" * 17_000},
            **common,
        )
    with pytest.raises(ValidationError, match="128 KiB"):
        WorkflowExecutionResult(
            workflow="alpha-data-admission",
            summary={"payload": "x" * 132_000},
            **common,
        )


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
    assert "not as a reason to declare the research question blocked" in prompt
    assert "left-closed, left-labeled, complete-bar resampling" in prompt
    assert "Never place a digest" in prompt
    assert "only exact pairs listed under" in prompt
    assert "Founder-idea IDs" in prompt
    assert "right-closed, left-labeled" not in prompt


def test_hypothesis_prompt_routes_visible_panels_to_lazy_admission():
    document = alpha_discovery_contract()
    document["stage"] = "hypothesis"
    document["context"]["lake_catalog"] = {
        "discovery_authority": True,
        "one_year_coverage_candidates": [
            {"venue": "bybit", "instrument": "ETHUSDT", "timeframe": "1m"}
        ],
    }

    prompt = _prompt(AlphaDiscoveryContract.model_validate(document))

    assert "Do not return an empty candidate list" in prompt
    assert "awaiting_data_admission" in prompt
    assert "before execution" in prompt


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
        "left_closed_left_labeled_complete_bars"
    ]


def test_representation_schema_is_outcome_blind_and_records_alternatives():
    schema = _schema("representation")
    plan = schema["properties"]["representation_plans"]["items"]
    required = set(plan["required"])
    assert {
        "schema_version",
        "candidate_key",
        "instruments",
        "basket_members",
        "source_timeframe",
        "research_timeframe",
        "resampling_policy",
        "transformation_rationale",
        "rejected_alternatives",
        "transformations",
        "selection_data_boundary",
        "outcome_data_consulted",
    }.issubset(required)
    assert plan["properties"]["source_timeframe"]["enum"] == ["1m"]
    assert plan["properties"]["outcome_data_consulted"]["const"] is False
    assert "fractional_difference" in plan["properties"]["transformations"][
        "items"
    ]["properties"]["operation"]["enum"]
    parameters = plan["properties"]["transformations"]["items"]["properties"][
        "parameters"
    ]
    assert parameters["additionalProperties"] is False
    assert set(parameters["required"]) == {
        "periods",
        "window",
        "d",
        "weight_threshold",
    }
    assert parameters["properties"]["periods"] == {
        "type": ["number", "null"],
        "minimum": 1,
        "maximum": 10_000,
    }
    assert parameters["properties"]["window"] == {
        "type": ["number", "null"],
        "minimum": 2,
        "maximum": 100_000,
    }
    transformation = plan["properties"]["transformations"]["items"]["properties"]
    assert transformation["output_field"]["pattern"] == "^[a-z][a-z0-9_]{0,99}$"
    input_pattern = transformation["input_fields"]["items"]["pattern"]
    assert "quote_volume" in input_pattern
    assert "A-Z0-9_-" in input_pattern


def test_representation_output_drops_unused_nullable_parameters():
    output = {
        "representation_plans": [
            {
                "transformations": [
                    {
                        "operation": "fractional_difference",
                        "parameters": {
                            "periods": None,
                            "window": None,
                            "d": 0.4,
                            "weight_threshold": 0.0001,
                        },
                    }
                ]
            }
        ]
    }

    normalized = _normalize_output("representation", output)

    assert normalized["representation_plans"][0]["transformations"][0][
        "parameters"
    ] == {"d": 0.4, "weight_threshold": 0.0001}


def test_representation_prompt_forbids_semantic_and_outcome_changes():
    document = alpha_discovery_contract()
    document["stage"] = "representation"
    document["context"]["raw_candidates"] = []
    prompt = _prompt(AlphaDiscoveryContract.model_validate(document))
    assert "do not change candidate questions" in prompt
    assert "before any outcome evaluation" in prompt
    assert "plausible rejected alternatives" in prompt
    assert "0 < d < 0.5" in prompt
    assert "one-observation rolling window is invalid" in prompt
    assert "Stable and volatile labels are descriptive" in prompt
    assert "metadata, never mandatory partitions" in prompt
    assert "instrument-qualified canonical panel columns" in prompt
    assert "BTCUSDT__close" in prompt
    assert "remain governed native-strategy inputs" in prompt
    assert "must not be copied into this transform graph" in prompt


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
