from pathlib import Path

import pytest
from pydantic import ValidationError

from swarm_worker.policy import AlphaResearchExecutionContract
from swarm_worker.workflows import WorkflowLoader


def test_native_execution_failure_is_bounded_retryable_source_contract() -> None:
    source = (
        Path(__file__).parents[1]
        / "src/swarm_worker/executors/alpha_research.py"
    ).read_text(encoding="utf-8")
    assert 'else "native_bulletproof_failed"' in source
    assert '"workflow_timeout"' in source
    assert "retryable=True" in source


def contract(**changes):
    payload = {
        "repository": "bulletproof_bt",
        "workflow": "alpha-research-execution",
        "base_ref": "a" * 40,
        "campaign_id": "11111111-1111-4111-8111-111111111111",
        "campaign_digest": "b" * 64,
        "source_candidate_id": "22222222-2222-4222-8222-222222222222",
        "source_candidate_digest": "c" * 64,
        "question": "Does the exact registered strategy survive costs?",
        "question_digest": "d" * 64,
        "domain_key": "systematic-quantitative-research",
        "dataset_build_id": "33333333-3333-4333-8333-333333333333",
        "dataset_digest": "e" * 64,
        "dataset_path": "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
        "memory_database": (
            "/home/omenka/.local/state/invariance-swarm/alpha002-memory.sqlite"
        ),
        "bundle_root": (
            "/home/omenka/.local/share/invariance-swarm/alpha002-bundles"
        ),
        "dataset_key": "bybit-btcusdt-perp-1m",
        "instrument": "BTCUSDT",
        "timeframe": "1m",
        "tier": "Tier2B",
        "max_variants": 8,
        "research_context": {"abstained": True, "citations": []},
        "authority": "no_capital",
    }
    payload.update(changes)
    return payload


def test_alpha_contract_and_fixed_workflow_are_narrow() -> None:
    value = AlphaResearchExecutionContract.model_validate(contract())
    workflow = WorkflowLoader(Path(__file__).parents[1] / "workflows").load(
        value.workflow
    )
    assert workflow.steps == []
    assert workflow.allowed_repositories == ["bulletproof_bt"]


@pytest.mark.parametrize(
    "changes",
    [
        {"authority": "live"},
        {"dataset_path": "/tmp/panel.parquet"},
        {"base_ref": "main"},
        {"max_variants": 0},
    ],
)
def test_alpha_contract_rejects_authority_path_and_budget_expansion(changes) -> None:
    with pytest.raises(ValidationError):
        AlphaResearchExecutionContract.model_validate(contract(**changes))
