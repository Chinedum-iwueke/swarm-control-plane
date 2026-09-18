import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from swarm_worker.executors.alpha_research import (
    AlphaResearchExecutionError,
    AlphaResearchExecutor,
    _qualification_handoff,
)


def test_capacity_telemetry_fails_closed_when_missing_or_stale(tmp_path):
    import json
    from datetime import UTC, datetime

    executor = AlphaResearchExecutor(heartbeat_interval_seconds=30,
                                    capacity_database=tmp_path / "db")
    assert executor.capacity_progress() == {"telemetry_current": False}
    state = tmp_path / "alpha-capacity-state.json"
    state.write_text(json.dumps({"updated_at": "2020-01-01T00:00:00+00:00"}))
    assert not executor.capacity_progress()["telemetry_current"]
    state.write_text(json.dumps({"updated_at": datetime.now(UTC).isoformat(),
                                "worker_slots": {"running": 16}, "jobs": []}))
    assert executor.capacity_progress()["worker_slots"]["running"] == 16
    assert executor.capacity_progress()["telemetry_current"]
from swarm_worker.models import WorkflowExecutionResult
from swarm_worker.policy import AlphaResearchExecutionContract
from swarm_worker.workflows import WorkflowLoader


def test_native_execution_failure_is_bounded_retryable_source_contract() -> None:
    source = (
        Path(__file__).parents[1] / "src/swarm_worker/executors/alpha_research.py"
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
        "bundle_root": ("/home/omenka/.local/share/invariance-swarm/alpha002-bundles"),
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


def test_alpha003_qualification_requires_card_and_founder_receipt() -> None:
    shared = {
        "stage": "qualify",
        "venue": "bybit",
        "window_start": "2026-04-01T00:00:00Z",
        "window_end": "2026-05-01T00:00:00Z",
    }
    with pytest.raises(ValidationError, match="founder approval"):
        AlphaResearchExecutionContract.model_validate(contract(**shared))
    value = AlphaResearchExecutionContract.model_validate(
        contract(
            **shared,
            hypothesis_card={"schema_version": "hypothesis_card_v1"},
            card_approval={"actor": "founder-operator", "plan_digest": "f" * 64},
        )
    )
    assert value.stage == "qualify"


def test_alpha_contract_binds_exact_basket_and_arbitrary_safe_resample() -> None:
    bindings = [
        {
            "dataset_build_id": "33333333-3333-4333-8333-333333333333",
            "dataset_digest": "e" * 64,
            "dataset_path": "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
            "dataset_key": "bybit-btcusdt-perp-1m",
            "instrument": "BTCUSDT",
            "venue": "bybit",
        },
        {
            "dataset_build_id": "44444444-4444-4444-8444-444444444444",
            "dataset_digest": "f" * 64,
            "dataset_path": "/home/omenka/Projects/bulletproof_bt/research_data/eth.parquet",
            "dataset_key": "bybit-ethusdt-perp-1m",
            "instrument": "ETHUSDT",
            "venue": "bybit",
        },
    ]
    value = AlphaResearchExecutionContract.model_validate(
        contract(
            dataset_bindings=bindings,
            instruments=["BTCUSDT", "ETHUSDT"],
            research_timeframe="7m",
            resampling_policy="right_closed_left_labeled_complete_bars",
        )
    )
    assert value.research_timeframe == "7m"
    assert value.resampling_policy == "left_closed_left_labeled_complete_bars"
    assert [item.instrument for item in value.dataset_bindings] == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    with pytest.raises(ValidationError, match="basket must match"):
        AlphaResearchExecutionContract.model_validate(
            contract(dataset_bindings=bindings, instruments=["ETHUSDT", "BTCUSDT"])
        )


def test_alpha_contract_binds_frozen_reusable_native_strategy() -> None:
    reusable = {
        "hypothesis_id": "ALPHA-WEEKEND-MOMENTUM",
        "strategy": "alpha_weekend_momentum",
        "input_mode": "single_instrument",
        "maximum_instruments": 1,
        "contract_path": "research/hypotheses/alpha_weekend_momentum.yaml",
        "contract_digest": "f" * 64,
        "variant_count": 8,
        "bounded_weekly_reuse_eligible": True,
    }
    value = AlphaResearchExecutionContract.model_validate(
        contract(reusable_strategy=reusable)
    )
    assert value.reusable_strategy == reusable
    with pytest.raises(ValidationError, match="not weekly eligible"):
        AlphaResearchExecutionContract.model_validate(
            contract(
                reusable_strategy={
                    **reusable,
                    "bounded_weekly_reuse_eligible": False,
                }
            )
        )


def test_commissioning_contract_is_short_bounded_and_review_contained() -> None:
    qualification = {
        "qualified": True,
        "window": {
            "start": "2023-01-01T00:00:00Z",
            "end": "2024-01-01T00:00:00Z",
        },
    }
    value = AlphaResearchExecutionContract.model_validate(
        contract(
            stage="execute",
            execution_class="commissioning",
            venue="bybit",
            window_start="2023-01-01T00:00:00Z",
            window_end="2023-02-01T00:00:00Z",
            qualification=qualification,
        )
    )
    assert value.execution_class == "commissioning"

    with pytest.raises(ValidationError, match="at most 31 days"):
        AlphaResearchExecutionContract.model_validate(
            contract(
                stage="execute",
                execution_class="commissioning",
                venue="bybit",
                window_start="2023-01-01T00:00:00Z",
                window_end="2023-03-01T00:00:00Z",
                qualification=qualification,
            )
        )
    with pytest.raises(ValidationError, match="contained"):
        AlphaResearchExecutionContract.model_validate(
            contract(
                stage="execute",
                execution_class="commissioning",
                venue="bybit",
                window_start="2022-12-15T00:00:00Z",
                window_end="2023-01-15T00:00:00Z",
                qualification=qualification,
            )
        )


def test_qualification_handoff_retains_execution_inputs_inside_downstream_limit() -> None:
    qualification = {
        "schema_version": "alpha-strategy-qualification-v1.0.0",
        "qualified": True,
        "card": {"title": "Weekend momentum", "claim": "x" * 5_500},
        "card_digest": "a" * 64,
        "review": {"gates": {"independent_review_complete": True}},
        "variant_count": 8,
        "artifact_bundle": {
            "card": {"duplicated": "x" * 20_000},
            "hypothesis_spec": {
                "hypothesis_id": "h1",
                "source_card_hash": "a" * 64,
                "duplicated": "x" * 20_000,
            },
            "normalized_ir": {"duplicated": "x" * 20_000},
            "engine_hypothesis_yaml": {"metadata": {"hypothesis_id": "h1"}},
            "strategy_spec": {"strategy": {"name": "alpha_weekend_momentum"}},
        },
    }

    handoff = _qualification_handoff(qualification)

    assert set(handoff["artifact_bundle"]) == {
        "engine_hypothesis_yaml",
        "strategy_spec",
    }
    encoded_hypothesis = json.dumps(
        qualification["artifact_bundle"]["hypothesis_spec"],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert handoff["hypothesis_contract"] == {
        "hypothesis_id": "h1",
        "source_card_hash": "a" * 64,
        "hypothesis_digest": hashlib.sha256(encoded_hypothesis).hexdigest(),
    }
    result = WorkflowExecutionResult(
        workflow="alpha-research-execution",
        repository="bulletproof_bt",
        base_commit="a" * 40,
        task_attempt=1,
        total_duration_seconds=1,
        steps=[],
        success=True,
        summary={
            "qualification_receipt": {
                "qualified": handoff["qualified"],
                "card_digest": handoff["card_digest"],
                "variant_count": handoff["variant_count"],
            }
        },
        downstream_handoff={"qualification": handoff},
    )
    assert result.downstream_handoff["qualification"] == handoff


def test_qualification_handoff_fails_closed_without_execution_artifact() -> None:
    with pytest.raises(AlphaResearchExecutionError, match="execution artifact"):
        _qualification_handoff(
            {
                "qualified": True,
                "artifact_bundle": {"engine_hypothesis_yaml": {}},
            }
        )


def test_large_publication_envelope_uses_bounded_downstream_handoff() -> None:
    publication_envelope = {
        "schema_version": "alpha003-publication-envelope-v1.0.0",
        "bridge_proposal": {"source": {"evidence": "x" * 7_000}},
        "hypothesis_card": {"citations": "y" * 5_000},
        "trial": {"selection_bias_audit": "z" * 3_000},
    }
    result = WorkflowExecutionResult(
        workflow="alpha-research-execution",
        repository="bulletproof_bt",
        base_commit="a" * 40,
        task_attempt=1,
        total_duration_seconds=1,
        steps=[],
        success=True,
        summary={"disposition": "native_execution_complete"},
        downstream_handoff={"publication_envelope": publication_envelope},
    )

    assert result.downstream_handoff["publication_envelope"] == publication_envelope


def test_commissioning_summary_retains_bounded_proof_fields() -> None:
    receipt = {
        "record_digest": "f" * 64,
        "variant_count": 8,
        "selected_variant_index": 3,
        "window": {
            "start": "2023-01-01T00:00:00+00:00",
            "end": "2023-02-01T00:00:00+00:00",
        },
        "large_truth_report": "x" * 40_000,
    }
    bounded = {
        key: receipt[key]
        for key in (
            "record_digest",
            "variant_count",
            "selected_variant_index",
            "window",
        )
    }
    result = WorkflowExecutionResult(
        workflow="alpha-research-execution",
        repository="bulletproof_bt",
        base_commit="a" * 40,
        task_attempt=1,
        total_duration_seconds=1,
        steps=[],
        success=True,
        summary={"commissioning_receipt": bounded},
    )
    assert result.summary["commissioning_receipt"] == bounded


def test_downstream_handoff_remains_bounded() -> None:
    with pytest.raises(ValidationError, match="downstream handoff exceeds 32 KiB"):
        WorkflowExecutionResult(
            workflow="alpha-research-execution",
            repository="bulletproof_bt",
            base_commit="a" * 40,
            task_attempt=1,
            total_duration_seconds=1,
            steps=[],
            success=True,
            downstream_handoff={"payload": "x" * 33_000},
        )


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
