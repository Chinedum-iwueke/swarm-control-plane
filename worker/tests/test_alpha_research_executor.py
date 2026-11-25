import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from swarm_worker.executors.alpha_research import (
    AlphaResearchExecutionError,
    AlphaResearchExecutor,
    _publication_handoff,
    _qualification_handoff,
    _execution_preparation_handoff,
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


def test_capacity_queue_uses_host_runtime_not_pinned_strategy_checkout(
    tmp_path,
) -> None:
    queue_script = tmp_path / "installed" / "queue_alpha_capacity_assignment.py"
    executor = AlphaResearchExecutor(
        heartbeat_interval_seconds=30,
        capacity_queue_script=queue_script,
    )

    assert executor._capacity_queue_script == queue_script
    assert (
        "workspace.repository"
        not in (
            Path(__file__).parents[1] / "src/swarm_worker/executors/alpha_research.py"
        )
        .read_text(encoding="utf-8")
        .split(
            'if self._capacity_database is not None and contract.stage == "execute":', 1
        )[1]
        .split("env =", 1)[0]
    )


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


def test_prepare_execution_stage_cannot_fall_back_to_execute():
    with pytest.raises(ValidationError, match="requires template"):
        AlphaResearchExecutionContract.model_validate(contract(stage="prepare_execution"))
    with pytest.raises(ValidationError):
        AlphaResearchExecutionContract.model_validate(contract(stage="unknown"))


def preparation_contract():
    base = contract()
    binding = {key:base[key] for key in ('dataset_build_id','dataset_digest','dataset_path','dataset_key','instrument')}
    binding['venue'] = 'bybit'
    plan = dict(schema_version='adaptive-representation-plan-v1.0.0', candidate_key='prospective',
        instruments=['BTCUSDT'], basket_members=[dict(instrument='BTCUSDT',role='primary',legacy_groups=[],selection_rationale='Primary asset.')],
        source_timeframe='1m', research_timeframe='1m', resampling_policy='left_closed_left_labeled_complete_bars',
        transformations=[dict(operation='log_return',input_fields=['BTCUSDT__close'],output_field='return',parameters={'periods':1},fit_policy='stateless',rationale='Causal return.')],
        transformation_rationale='Completed observations only.', rejected_alternatives=['Future observations.'],
        selection_data_boundary='metadata_predictors_only_no_targets',outcome_data_consulted=False)
    window = dict(start='2026-04-01T00:00:00Z',end='2026-05-01T00:00:00Z')
    return contract(stage='prepare_execution', venue='bybit', window_start=window['start'],window_end=window['end'],
        dataset_bindings=[binding], instruments=['BTCUSDT'],representation_plan=plan,
        reusable_strategy=dict(hypothesis_id='example',strategy='registered',input_mode='single_instrument',
            maximum_instruments=1,contract_path='research/hypotheses/example.yaml',contract_digest='a'*64,
            variant_count=1,bounded_weekly_reuse_eligible=True),
        released_execution_preparation=dict(schema_version='released-execution-preparation-v1',
            expected_template_digest='a'*64,expected_method_digest='b'*64,engineering_bundle_digest='c'*64,
            accepted_representation=deepcopy(plan),representation_transition={},
            native_dataset_bindings=[deepcopy(binding)],validation_requirements={},approved_window=window,
            expected_plans={mode:{'source_commit':base['base_ref']} for mode in ('smoke','scientific')}))


def test_preparation_contract_preserves_native_metadata_losslessly():
    payload = preparation_contract()
    payload['released_execution_preparation']['native_dataset_bindings'][0]['rows'] = 12345
    value = AlphaResearchExecutionContract.model_validate(payload)
    assert value.released_execution_preparation.model_dump() == payload['released_execution_preparation']


def full_native_binding():
    binding = deepcopy(preparation_contract()['dataset_bindings'][0])
    binding.update(rows=12345, instruments=['BTCUSDT'],
        catalog_id='11111111-1111-4111-8111-111111111111',
        producer_receipt_id='22222222-2222-4222-8222-222222222222',
        lake_governance_snapshot_id='33333333-3333-4333-8333-333333333333',
        builder_commit='a'*40, admission_source_commit='b'*40,
        output_columns=['ts','close','quote_volume'], partition_digests=['f'*64],partition_digest='f'*64,
        catalog_digest='1'*64,manifest_digest='2'*64,producer_receipt_digest='3'*64,lake_governance_digest='4'*64,
        evidence_class='live_exchange_history',research_principal='alpha-research-runner')
    return binding


def test_native_binding_survives_worker_contract_roundtrip():
    binding = full_native_binding()
    value = AlphaResearchExecutionContract.model_validate(contract(dataset_bindings=[binding],instruments=['BTCUSDT']))
    assert value.model_dump()['dataset_bindings'] == [binding]
    assert AlphaResearchExecutionContract.model_validate(value.model_dump()).model_dump() == value.model_dump()


def test_native_multi_partition_binding_has_no_false_singular_identity():
    binding = full_native_binding()
    binding['partition_digests'].append('e'*64)
    binding['partition_digest'] = None
    value = AlphaResearchExecutionContract.model_validate(contract(dataset_bindings=[binding],instruments=['BTCUSDT']))
    assert value.dataset_bindings[0].partition_digests == binding['partition_digests']


@pytest.mark.parametrize('failure', ['partial','extra','instrument','partition','duplicate','admission'])
def test_native_binding_rejects_partial_or_inconsistent_evidence(failure):
    binding = full_native_binding()
    if failure == 'partial': del binding['catalog_id']
    elif failure == 'extra': binding['unreviewed_override'] = True
    elif failure == 'instrument': binding['instruments'] = ['ETHUSDT']
    elif failure == 'partition': binding['partition_digest'] = 'e'*64
    elif failure == 'duplicate': binding['partition_digests'].append('f'*64)
    else: binding['producer_receipt_digest'] = None
    with pytest.raises(ValidationError):
        AlphaResearchExecutionContract.model_validate(contract(dataset_bindings=[binding],instruments=['BTCUSDT']))


@pytest.mark.parametrize('failure', ['data','source','representation','execute','commissioning','qualification'])
def test_preparation_rejects_changed_identity_or_execution_authority(failure):
    payload = preparation_contract()
    prep = payload['released_execution_preparation']
    if failure == 'data': prep['native_dataset_bindings'][0]['dataset_digest'] = 'f'*64
    elif failure == 'source': prep['expected_plans']['smoke']['source_commit'] = 'f'*40
    elif failure == 'representation': prep['accepted_representation']['candidate_key'] = 'changed'
    elif failure == 'execute': payload['stage'] = 'execute'
    elif failure == 'commissioning': payload['execution_class'] = 'commissioning'
    else: payload['qualification'] = {'qualified':True}
    with pytest.raises(ValidationError):
        AlphaResearchExecutionContract.model_validate(payload)


def test_prepared_card_handoff_retains_full_prospective_evidence():
    card = {"status": "draft", "claim": "A prospective claim"}
    document = dict(hypothesis_card=card,
        card_digest=hashlib.sha256(json.dumps(card, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        prepared_binding={"contract": {"science": "retained"}, "lineage": {"parent": "unchanged"}},
        representation_transition={"narrative_changes": [{"before": "x", "after": "y"}]},
        execution_authority=False)
    assert _execution_preparation_handoff(document) == document
    document["hypothesis_card"]["claim"] = "changed"
    with pytest.raises(AlphaResearchExecutionError, match="digest mismatch"):
        _execution_preparation_handoff(document)


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
            representation_plan={
                "schema_version": "adaptive-representation-plan-v1.0.0",
                "candidate_key": "mixed-basket",
                "instruments": ["BTCUSDT", "ETHUSDT"],
                "basket_members": [
                    {
                        "instrument": "BTCUSDT",
                        "role": "primary",
                        "legacy_groups": ["stable"],
                        "selection_rationale": "Primary asset named by the question.",
                    },
                    {
                        "instrument": "ETHUSDT",
                        "role": "control",
                        "legacy_groups": ["volatile"],
                        "selection_rationale": "Cross-group control for market movement.",
                    },
                ],
                "source_timeframe": "1m",
                "research_timeframe": "7m",
                "resampling_policy": "left_closed_left_labeled_complete_bars",
                "transformations": [
                    {
                        "output_field": "btc_return",
                        "operation": "log_return",
                        "input_fields": ["BTCUSDT__close"],
                        "parameters": {"periods": 1},
                        "fit_policy": "stateless",
                        "rationale": "Represent the price level as a scale-safe return.",
                    }
                ],
                "transformation_rationale": "Seven-minute bars match the causal horizon.",
                "rejected_alternatives": ["One-minute bars are too noisy."],
                "selection_data_boundary": "metadata_predictors_only_no_targets",
                "outcome_data_consulted": False,
            },
        )
    )
    assert value.research_timeframe == "7m"
    assert value.resampling_policy == "left_closed_left_labeled_complete_bars"
    assert [item.instrument for item in value.dataset_bindings] == [
        "BTCUSDT",
        "ETHUSDT",
    ]
    assert value.representation_plan["basket_members"][1]["role"] == "control"
    with pytest.raises(ValidationError, match="basket must match"):
        AlphaResearchExecutionContract.model_validate(
            contract(dataset_bindings=bindings, instruments=["ETHUSDT", "BTCUSDT"])
        )


def test_alpha_contract_retains_complete_trusted_dataset_evidence() -> None:
    trusted = {
        "catalog_digest": "1" * 64,
        "manifest_digest": "2" * 64,
        "producer_receipt_digest": "3" * 64,
        "lake_governance_digest": "4" * 64,
        "partition_digest": "5" * 64,
    }
    binding = {
        "dataset_build_id": "33333333-3333-4333-8333-333333333333",
        "dataset_digest": "e" * 64,
        "dataset_path": "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
        "dataset_key": "bybit-btcusdt-perp-1m",
        "instrument": "BTCUSDT",
        "venue": "bybit",
        **trusted,
    }

    value = AlphaResearchExecutionContract.model_validate(
        contract(dataset_bindings=[binding], instruments=["BTCUSDT"])
    )

    assert value.model_dump(mode="json")["dataset_bindings"][0] == binding


def test_alpha_contract_rejects_partial_trusted_dataset_evidence() -> None:
    binding = {
        "dataset_build_id": "33333333-3333-4333-8333-333333333333",
        "dataset_digest": "e" * 64,
        "dataset_path": "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
        "dataset_key": "bybit-btcusdt-perp-1m",
        "instrument": "BTCUSDT",
        "venue": "bybit",
        "catalog_digest": "1" * 64,
    }

    with pytest.raises(ValidationError, match="all immutable digests"):
        AlphaResearchExecutionContract.model_validate(
            contract(dataset_bindings=[binding], instruments=["BTCUSDT"])
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
    overlap_document = {
        "schema_version": "alpha-basket-overlap-admission-v1.0.0",
        "authority": "DATA-002/003",
        "dataset_bindings": [],
        "instruments": ["ETHUSDT", "SOLUSDT"],
        "minimum_contiguous_days": 365,
        "admitted_start": "2023-01-01T00:00:00+00:00",
        "admitted_end": "2024-01-01T00:00:00+00:00",
    }
    overlap_receipt = {
        **overlap_document,
        "record_digest": hashlib.sha256(
            json.dumps(
                overlap_document, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
    }
    qualification = {
        "schema_version": "alpha-strategy-qualification-v1.0.0",
        "qualified": True,
        "card": {"title": "Weekend momentum", "claim": "x" * 5_500},
        "card_digest": "a" * 64,
        "review": {"gates": {"independent_review_complete": True}},
        "variant_count": 8,
        "overlap_admission_receipt": overlap_receipt,
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
    assert handoff["overlap_admission_receipt"] == overlap_receipt
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


def released_qualification():
    def signed(document, key):
        return {**document, key: hashlib.sha256(json.dumps(
            document, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()).hexdigest()}
    contract = {"immutable_contract": {"source_commit": "a" * 40}}
    binding = signed({
        "schema_version": "released-execution-contract-binding-v1",
        "source_commit": "a" * 40,
        "prepared_contract_digest": hashlib.sha256(json.dumps(
            contract, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "requires_independent_execution_review": True, "execution_authority": False,
    }, "binding_digest")
    transition = signed({
        "schema_version": "released-representation-transition-v1",
        "release_source_commit": "a" * 40, "execution_authority": False,
        "historical_documents_mutated": False,
        "narrative_changes": [{"path": "/transformation_rationale", "accepted": "before", "released": "after"}],
    }, "evidence_digest")
    return {"qualification_scope": "released_execution_compilation_only", "qualified": False,
            "artifact_bundle": {"engine_hypothesis_yaml": contract, "strategy_spec": {},
                "hypothesis_spec": {"hypothesis_id": "h1", "source_card_hash": "c" * 64},
                "released_execution_binding": binding, "representation_transition": transition}}


def test_released_handoff_preserves_review_evidence_without_granting_authority():
    qualification = released_qualification()
    retained = _qualification_handoff(qualification)
    assert retained["qualified"] is False
    assert retained["qualification_scope"] == qualification["qualification_scope"]
    for key in ("released_execution_binding", "representation_transition"):
        assert retained["artifact_bundle"][key] == qualification["artifact_bundle"][key]


@pytest.mark.parametrize("corruption", ["missing_transition", "modified_transition", "modified_contract", "modified_binding"])
def test_released_handoff_rejects_lost_or_modified_evidence(corruption):
    qualification = released_qualification()
    bundle = qualification["artifact_bundle"]
    if corruption == "missing_transition":
        del bundle["representation_transition"]
    elif corruption == "modified_transition":
        bundle["representation_transition"]["narrative_changes"] = []
    elif corruption == "modified_contract":
        bundle["engine_hypothesis_yaml"]["immutable_contract"]["source_commit"] = "b" * 40
    else:
        bundle["released_execution_binding"]["execution_authority"] = True
    with pytest.raises(AlphaResearchExecutionError, match="Released execution evidence"):
        _qualification_handoff(qualification)


def test_qualification_handoff_rejects_mutated_overlap_receipt() -> None:
    with pytest.raises(AlphaResearchExecutionError, match="overlap admission"):
        _qualification_handoff(
            {
                "qualified": True,
                "artifact_bundle": {
                    "engine_hypothesis_yaml": {},
                    "strategy_spec": {},
                    "hypothesis_spec": {
                        "hypothesis_id": "h1",
                        "source_card_hash": "a" * 64,
                    },
                },
                "overlap_admission_receipt": {
                    "schema_version": "alpha-basket-overlap-admission-v1.0.0",
                    "authority": "DATA-002/003",
                    "record_digest": "0" * 64,
                },
            }
        )


def test_large_publication_envelope_uses_bounded_downstream_handoff() -> None:
    publication_envelope = {
        "schema_version": "alpha003-publication-envelope-v1.0.0",
        "bridge_proposal": {"source": {"question": "bounded question"}},
        "hypothesis_card": {"citations": ["retained citation"]},
        "experiment": {"features": ["close"]},
        "memory_receipt": {"receipt_digest": "a" * 64},
        "producer_gate_report": {"failed_gates": ["insufficient support"]},
        "execution_class": "qualification",
        "qualification_authority": True,
        "durable_bundle_path": "/durable/bundle",
        "trial": {
            "trial_id": "trial-1",
            "code_digest": "b" * 64,
            "metrics": {
                "oos_trades": 93,
                "selection_bias_audit": {
                    "matched_controls": ["metric-audit" * 1024] * 8,
                },
                "confidence_interval_95": [-0.1, 0.2],
            },
            "started_at": "2026-01-01T00:00:00+00:00",
            "ended_at": "2026-01-02T00:00:00+00:00",
            "truth": {"truth_certified": True},
            "bundle_digest": "c" * 64,
            "bundle_manifest_digest": "d" * 64,
            "market_model_bundle_digest": "e" * 64,
            "representation_contract_digest": "f" * 64,
            "search_plan_digest": "1" * 64,
            "selection_bias_audit": {
                "record_digest": "2" * 64,
                "matched_controls": ["x" * 1024] * 80,
            },
            "required_trade_logging_evaluation": {
                "record_digest": "3" * 64,
                "trade_log": ["y" * 1024] * 40,
            },
            "hypothesis_evaluation": {
                "outcome": "failed",
                "record_digest": "4" * 64,
                "reason": "no_supported_validation_variant",
                "large_diagnostics": ["z" * 1024] * 40,
            },
        },
    }
    handoff = _publication_handoff(publication_envelope)
    result = WorkflowExecutionResult(
        workflow="alpha-research-execution",
        repository="bulletproof_bt",
        base_commit="a" * 40,
        task_attempt=1,
        total_duration_seconds=1,
        steps=[],
        success=True,
        summary={"disposition": "native_execution_complete"},
        downstream_handoff={"publication_envelope": handoff},
    )

    retained = result.downstream_handoff["publication_envelope"]
    assert retained["trial"]["hypothesis_evaluation"] == {
        "outcome": "failed",
        "record_digest": "4" * 64,
        "reason": "no_supported_validation_variant",
    }
    assert "selection_bias_audit" not in retained["trial"]
    assert retained["trial"]["metrics"] == {"oos_trades": 93}
    assert retained["durable_evidence"]["selection_bias_audit_digest"] == "2" * 64
    assert retained["durable_evidence"]["required_trade_logging_digest"] == "3" * 64
    assert len(json.dumps(result.downstream_handoff, sort_keys=True)) < 32_768


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
