import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.alpha_campaign import router
from app.models.data_contract import ResearchDatasetBuild, ResearchDatasetManifest
from app.models.discovery_portfolio import (
    DiscoveryPortfolio,
)
from app.models.lake_operations import LakeGovernanceSnapshot
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.schemas.alpha_campaign import (
    AlphaCampaignAction,
    AlphaCampaignAttemptCreate,
    AlphaCampaignCreate,
    AlphaCompletedExecutionRecovery,
)
from app.schemas.proposal import ProposalEngineeringMissionContract
from app.services import alpha_campaign as service
from fastapi import HTTPException
from pydantic import ValidationError

DIGEST = "a" * 64
COMMIT = "b" * 40


def request(**updates):
    value = {
        "campaign_key": "ALPHA001-BYBIT-BTC",
        "version": "1.0.0",
        "project": "bulletproof-bt",
        "objective": "Continuously test bounded BTC perpetual hypotheses on admitted real exchange history.",
        "discovery_portfolio_id": uuid4(),
        "dataset_bindings": [
            {
                "dataset_build_id": uuid4(),
                "catalog_id": uuid4(),
                "lake_governance_snapshot_id": uuid4(),
                "producer_receipt_id": uuid4(),
                "dataset_key": "bybit-btcusdt-perp-1m",
                "partition_digests": [DIGEST],
                "evidence_class": "live_exchange_history",
                "research_principal": "alpha-research-runner",
            }
        ],
        "bulletproof_source_commit": COMMIT,
        "allowed_venues": ["bybit"],
        "allowed_instruments": ["BTCUSDT"],
        "budget": {
            "max_hypotheses": 2,
            "max_total_trials": 16,
            "max_variants_per_hypothesis": 8,
            "max_duration_seconds": 86400,
            "max_consecutive_failures": 2,
        },
        "created_by": "founder-operator",
    }
    value.update(updates)
    return AlphaCampaignCreate.model_validate(value)


def records(payload, *, provider_name="bybit-api"):
    binding = payload.dataset_bindings[0]
    portfolio = SimpleNamespace(
        id=payload.discovery_portfolio_id,
        project="bulletproof-bt",
        status="allocated",
        selected_count=1,
        allocation_digest="c" * 64,
    )
    candidate = SimpleNamespace(
        id=uuid4(),
        portfolio_id=portfolio.id,
        candidate_digest="5" * 64,
        question="Does lagged BTC displacement retain net predictive value after costs?",
        domain_key="systematic-quantitative-research",
        rank=1,
    )
    manifest = SimpleNamespace(
        id=uuid4(),
        manifest_digest="d" * 64,
        manifest={
            "provider": {
                "name": provider_name,
                "dataset": binding.dataset_key,
                "venue": "bybit",
            },
            "instruments": ["BTCUSDT"],
            "output_columns": ["ts", "open", "high", "low", "close", "volume"],
            "source_objects": [
                {"uri": "file:///lake/bybit/BTCUSDT/research_panel.parquet"}
            ],
        },
    )
    build = SimpleNamespace(
        id=binding.dataset_build_id,
        manifest_id=manifest.id,
        builder_repository="bulletproof_bt",
        builder_commit=COMMIT,
        content_digest=DIGEST,
        rows=1_000_000,
    )
    catalog = SimpleNamespace(
        id=binding.catalog_id,
        catalog_digest="f" * 64,
        catalog={
            "partitions": [
                {
                    "dataset_key": binding.dataset_key,
                    "content_digest": DIGEST,
                    "layer": "curated",
                    "venue_id": "bybit",
                    "duplicate_count": 0,
                    "gap_count": 0,
                    "access_mode": "read_only",
                    "source_key": "bybit-api",
                }
            ],
            "source_availability": [{"source_key": "bybit-api", "status": "available"}],
        },
    )
    lake = SimpleNamespace(
        id=binding.lake_governance_snapshot_id,
        catalog_digest=catalog.catalog_digest,
        snapshot_digest="1" * 64,
        snapshot={
            "quality_slos": [{"dataset_key": binding.dataset_key, "layer": "curated"}],
            "entitlements": [
                {
                    "principal": "alpha-research-runner",
                    "dataset_keys": [binding.dataset_key],
                    "actions": ["read"],
                    "purpose": "research",
                }
            ],
        },
    )
    producer_receipt = SimpleNamespace(
        id=binding.producer_receipt_id,
        milestone="ALPHA-001",
        producer="bt.institutional.alpha.real_data_admission_receipt",
        source_commit=COMMIT,
        dataset_digest=build.content_digest,
        receipt_digest="4" * 64,
        receipt={
            "result": {
                "evidence_class": "live_exchange_history",
                "admitted": True,
                "venue": "bybit",
                "instrument": "BTCUSDT",
                "row_count": 1_000_000,
                "output_columns": [
                    "ts",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "quote_volume",
                ],
            },
            "authority": {
                "allocation": False,
                "capital": False,
                "orders": False,
                "promotion": False,
            },
        },
    )
    return portfolio, candidate, manifest, build, catalog, lake, producer_receipt


def database(payload, *, provider_name="bybit-api"):
    db = MagicMock()
    portfolio, candidate, manifest, build, catalog, lake, producer_receipt = records(
        payload, provider_name=provider_name
    )

    def get(model, identity):
        values = {
            (DiscoveryPortfolio, portfolio.id): portfolio,
            (ResearchDatasetBuild, build.id): build,
            (ResearchDatasetManifest, manifest.id): manifest,
            (MarketDataCatalogSnapshot, catalog.id): catalog,
            (LakeGovernanceSnapshot, lake.id): lake,
            (QuantitativeProducerReceipt, producer_receipt.id): producer_receipt,
        }
        return values.get((model, identity))

    db.get.side_effect = get
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = [candidate]
    return db


def test_data_admission_and_strategy_source_commits_are_independently_pinned():
    payload = request()
    db = database(payload)
    producer_receipt = db.get(
        QuantitativeProducerReceipt, payload.dataset_bindings[0].producer_receipt_id
    )
    producer_receipt.source_commit = "c" * 40

    admitted = service.validate_real_data_bindings(db, payload)

    assert admitted[0]["admission_source_commit"] == "c" * 40
    assert admitted[0]["builder_commit"] == COMMIT
    assert payload.bulletproof_source_commit == COMMIT


def campaign(**updates):
    activated = datetime.now(UTC) - timedelta(minutes=1)
    value = {
        "id": uuid4(),
        "campaign_digest": DIGEST,
        "status": "running",
        "phase": "hypothesis",
        "next_action": "compile_evidence_grounded_hypothesis",
        "specification": {
            "bulletproof_source_commit": COMMIT,
            "dataset_bindings": [
                {
                    "dataset_build_id": str(uuid4()),
                    "dataset_digest": DIGEST,
                    "dataset_key": "bybit-btcusdt-perp-1m",
                    "venue": "bybit",
                    "instruments": ["BTCUSDT"],
                }
            ],
            "research_queue": [
                {
                    "source_candidate_id": str(uuid4()),
                    "source_candidate_digest": "5" * 64,
                    "question": "Does lagged BTC displacement retain net predictive value after costs?",
                    "domain_key": "systematic-quantitative-research",
                    "rank": 1,
                },
                {
                    "source_candidate_id": str(uuid4()),
                    "source_candidate_digest": "6" * 64,
                    "question": "Does BTC funding stress alter subsequent trend persistence after costs?",
                    "domain_key": "market-microstructure",
                    "rank": 2,
                },
            ],
        },
        "budget": {
            "max_hypotheses": 2,
            "max_total_trials": 16,
            "max_variants_per_hypothesis": 8,
            "max_duration_seconds": 86400,
            "max_consecutive_failures": 2,
        },
        "hypothesis_count": 0,
        "trial_count": 0,
        "consecutive_failures": 0,
        "candidate_attempt_id": None,
        "terminal_reason": {},
        "activated_at": activated,
        "heartbeat_at": activated,
        "completed_at": None,
    }
    value.update(updates)
    return SimpleNamespace(**value)


def test_campaign_resume_requires_recovered_governed_task(monkeypatch):
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="complete",
        next_action="operator_review",
        completed_at=datetime.now(UTC),
        terminal_reason={
            "category": "governed_pipeline_task_failed",
            "task_id": str(task_id),
        },
    )
    task = SimpleNamespace(id=task_id, status="succeeded")
    db = MagicMock()
    db.get.return_value = task
    events = []
    reconciled = []
    monkeypatch.setattr(
        service,
        "_append_event",
        lambda _db, _campaign, kind, actor, payload: events.append(
            (kind, actor, payload)
        ),
    )
    monkeypatch.setattr(
        service,
        "reconcile_campaign",
        lambda _db, value: reconciled.append(value),
    )

    service.resume_campaign(
        db,
        record,
        AlphaCampaignAction(
            expected_campaign_digest=DIGEST,
            actor="founder-operator",
            reason="Qualification retry completed successfully.",
        ),
    )

    assert record.status == "running"
    assert record.completed_at is None
    assert record.terminal_reason == {}
    assert events[0][0] == "campaign_resumed"
    assert events[0][2]["recovered_task_status"] == "succeeded"
    assert reconciled == [record]


def test_campaign_resume_rejects_task_that_is_still_failed() -> None:
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        terminal_reason={
            "category": "governed_pipeline_task_failed",
            "task_id": str(task_id),
        },
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=task_id,
        status="failed",
        task_number="A3-campaign-002-Q",
    )

    with pytest.raises(HTTPException, match="Resume the recorded pipeline task"):
        service.resume_campaign(
            db,
            record,
            AlphaCampaignAction(
                expected_campaign_digest=DIGEST,
                actor="founder-operator",
                reason="Try to resume before task recovery.",
            ),
        )


def test_campaign_resume_migrates_superseded_cancelled_engineering_task(monkeypatch):
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="complete",
        next_action="operator_review",
        completed_at=datetime.now(UTC),
        terminal_reason={
            "category": "governed_pipeline_task_cancelled",
            "task_id": str(task_id),
            "task_number": "A3-campaign-002-G",
        },
    )
    task = SimpleNamespace(
        id=task_id,
        status="cancelled",
        task_number="A3-campaign-002-G",
    )
    supersession = SimpleNamespace(
        payload={"successor_stage": "G2"},
    )
    db = MagicMock()
    db.get.return_value = task
    db.scalar.return_value = supersession
    events = []
    reconciled = []
    monkeypatch.setattr(
        service,
        "_append_event",
        lambda _db, _campaign, kind, actor, payload: events.append(
            (kind, actor, payload)
        ),
    )
    monkeypatch.setattr(
        service,
        "reconcile_campaign",
        lambda _db, value: reconciled.append(value),
    )

    service.resume_campaign(
        db,
        record,
        AlphaCampaignAction(
            expected_campaign_digest=DIGEST,
            actor="founder-operator",
            reason="Migrate the retained obsolete engineering contract to G3.",
        ),
    )

    assert record.status == "running"
    assert record.completed_at is None
    assert events[0][2]["obsolete_task_retained"] is True
    assert events[0][2]["recovered_task_status"] == "cancelled"
    assert reconciled == [record]


def test_campaign_resume_rejects_cancelled_engineering_without_supersession() -> None:
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        terminal_reason={
            "category": "governed_pipeline_task_cancelled",
            "task_id": str(task_id),
        },
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        id=task_id,
        status="cancelled",
        task_number="A3-campaign-002-G",
    )
    db.scalar.return_value = None

    with pytest.raises(HTTPException, match="Resume the recorded pipeline task"):
        service.resume_campaign(
            db,
            record,
            AlphaCampaignAction(
                expected_campaign_digest=DIGEST,
                actor="founder-operator",
                reason="Unsafe cancellation must remain terminal.",
            ),
        )


def test_publication_envelope_prefers_bounded_downstream_handoff() -> None:
    legacy = {"schema_version": "legacy"}
    handoff = {"schema_version": "alpha003-publication-envelope-v1.0.0"}

    result = service._publication_envelope_from_result(
        {
            "summary": {"publication_envelope": legacy},
            "downstream_handoff": {"publication_envelope": handoff},
        }
    )

    assert result == handoff


def test_publication_envelope_accepts_legacy_summary_result() -> None:
    legacy = {"schema_version": "alpha002-publication-envelope-v1.0.0"}

    result = service._publication_envelope_from_result(
        {"summary": {"publication_envelope": legacy}}
    )

    assert result == legacy


def test_qualification_prefers_bounded_downstream_handoff() -> None:
    legacy = {"qualified": False}
    handoff = {"qualified": True, "card_digest": "a" * 64}

    result = service._qualification_from_result(
        {
            "summary": {"qualification": legacy},
            "downstream_handoff": {"qualification": handoff},
        }
    )

    assert result == handoff


def test_pre_review_qualification_routes_only_when_deterministic_gates_pass():
    qualification = {
        "qualified": False,
        "card": {"independent_review_required": True},
        "review": {
            "blockers": [],
            "gates": {
                "schema_valid": True,
                "causality_valid": True,
                "strategy_compilable": True,
                "leakage_review_passed": True,
                "auxiliary_joins_backward": True,
                "independent_review_complete": False,
            },
        },
    }

    assert service._qualification_ready_for_independent_review(qualification)

    failed = deepcopy(qualification)
    failed["review"]["gates"]["causality_valid"] = False
    assert not service._qualification_ready_for_independent_review(failed)

    blocked = deepcopy(qualification)
    blocked["review"]["blockers"] = ["native strategy is unavailable"]
    assert not service._qualification_ready_for_independent_review(blocked)


def test_approved_independent_review_promotes_execution_qualification():
    qualification = {
        "qualified": False,
        "qualification_scope": "deterministic_compilation_only",
        "review": {
            "review_digest": "0" * 64,
            "blockers": [],
            "gates": {
                "schema_valid": True,
                "causality_valid": True,
                "strategy_compilable": True,
                "leakage_review_passed": True,
                "auxiliary_joins_backward": True,
                "independent_review_complete": False,
            },
            "independent_of_drafter": False,
        },
    }
    route = SimpleNamespace(id=uuid4())
    independence = SimpleNamespace(
        receipt_digest="1" * 64,
        assertion={"schema_version": "evaluation-independence-assertion-v1.0.0"},
        verdict="independence_demonstrated",
    )

    result = service._complete_independent_qualification(
        qualification,
        review_route=route,
        independence=independence,
        subject={"card_digest": "2" * 64},
    )

    assert result["qualified"] is True
    assert result["qualification_scope"] == "independently_reviewed_execution"
    assert result["review"]["gates"]["independent_review_complete"] is True
    assert result["review"]["independent_of_drafter"] is True
    assert result["governed_review"]["receipt_digest"] == "1" * 64
    assert result["review"][
        "governed_review_receipt_digest"
    ] == service.digest_document(result["governed_review"])
    assert qualification["qualified"] is False
    assert qualification["review"]["gates"]["independent_review_complete"] is False


def test_malformed_pending_execution_is_immutably_superseded(monkeypatch):
    task = SimpleNamespace(
        id=uuid4(),
        status="pending_approval",
        input_contract={"qualification": {"qualified": False}},
    )
    approval = SimpleNamespace(status="pending")
    db = MagicMock()
    db.scalar.return_value = approval
    decided = MagicMock()
    event = MagicMock()
    monkeypatch.setattr(service, "decide_task", decided)
    monkeypatch.setattr(service, "append_task_event", event)

    service._supersede_malformed_execution_task(db, task, successor_stage="E2")

    decided.assert_called_once_with(
        db,
        approval,
        actor="alpha-campaign-director",
        reason=(
            "Superseded by an immutable execution contract that incorporates the "
            "completed independent-review qualification."
        ),
        action="reject",
    )
    event.assert_called_once()
    assert event.call_args.kwargs["payload"] == {"successor_stage": "E2"}


def test_execution_task_prefers_repaired_successor():
    record = campaign()
    source = record.specification["research_queue"][0]
    repaired = SimpleNamespace(task_number="A3-repaired-001-E2")
    db = MagicMock()
    db.scalar.return_value = repaired

    assert service._execution_task(db, record, source) is repaired
    assert db.scalar.call_count == 1


def test_stale_execution_contracts_are_retained_but_made_unleaseable(monkeypatch):
    record = campaign()
    source = record.specification["research_queue"][0]
    pending = SimpleNamespace(
        id=uuid4(),
        task_number=service._stage_task_number(record, source, "E2"),
        status="pending_approval",
        cancel_requested_at=None,
        cancel_reason=None,
        completed_at=None,
    )
    queued = SimpleNamespace(
        id=uuid4(),
        task_number=service._stage_task_number(record, source, "E"),
        status="queued",
        cancel_requested_at=None,
        cancel_reason=None,
        completed_at=None,
    )
    pending_approval = SimpleNamespace(status="pending")
    approved_approval = SimpleNamespace(status="approved")
    db = MagicMock()
    db.scalar.side_effect = [pending, pending_approval, queued, approved_approval]
    decide = MagicMock()
    clear = MagicMock()
    discard = MagicMock()
    task_event = MagicMock()
    campaign_event = MagicMock()
    monkeypatch.setattr(service, "decide_task", decide)
    monkeypatch.setattr(service, "clear_lease", clear)
    monkeypatch.setattr("app.services.agent_context.discard_working_memory", discard)
    monkeypatch.setattr(service, "append_task_event", task_event)
    monkeypatch.setattr(service, "_append_event", campaign_event)
    qualification_task_id = uuid4()

    retired = service._retire_stale_execution_tasks(
        db,
        record,
        source,
        qualification_task_id=qualification_task_id,
    )

    assert retired == [pending, queued]
    assert pending.status == "cancelled"
    assert queued.status == "cancelled"
    assert decide.call_args_list[0].kwargs["action"] == "reject"
    assert decide.call_args_list[1].kwargs["action"] == "revoke"
    assert clear.call_count == 2
    assert discard.call_count == 2
    assert task_event.call_count == 2
    assert all(call.args[2] == "task_cancelled" for call in task_event.call_args_list)
    campaign_event.assert_called_once()
    payload = campaign_event.call_args.args[4]
    assert payload["reason"] == "qualification_dataset_binding_mismatch"
    assert payload["task_ids"] == [str(pending.id), str(queued.id)]


def test_active_stale_execution_contract_requests_cooperative_stop(monkeypatch):
    record = campaign()
    source = record.specification["research_queue"][0]
    running = SimpleNamespace(
        id=uuid4(),
        task_number=service._stage_task_number(record, source, "E2"),
        status="running",
        cancel_requested_at=None,
        cancel_reason=None,
    )
    db = MagicMock()
    db.scalar.side_effect = [running, None, None]
    task_event = MagicMock()
    monkeypatch.setattr(service, "append_task_event", task_event)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    retired = service._retire_stale_execution_tasks(
        db,
        record,
        source,
        qualification_task_id=uuid4(),
    )

    assert retired == [running]
    assert running.status == "running"
    assert running.cancel_requested_at is not None
    task_event.assert_called_once()
    assert task_event.call_args.args[2] == "task_cancellation_requested"
    assert task_event.call_args.kwargs["payload"]["cooperative"] is True


@pytest.mark.parametrize(
    ("category", "next_action"),
    [
        (
            "qualification_dataset_binding_mismatch",
            "rebind_native_strategy_to_admitted_data_evidence",
        ),
        (
            "qualification_overlap_admission_missing_or_invalid",
            "requalify_native_strategy_with_overlap_admission",
        ),
    ],
)
def test_reconcile_retires_stale_execution_from_parked_campaign(
    monkeypatch, category, next_action
):
    qualification_task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="strategy_qualification",
        next_action=next_action,
        terminal_reason={
            "category": category,
            "qualification_task_id": str(qualification_task_id),
            "retired_execution_task_ids": [str(uuid4())],
        },
    )
    newly_retired = SimpleNamespace(id=uuid4())
    retire = MagicMock(return_value=[newly_retired])
    db = MagicMock()
    monkeypatch.setattr(service, "_retire_stale_execution_tasks", retire)
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: None)

    service.reconcile_campaign(db, record)

    retire.assert_called_once_with(
        db,
        record,
        record.specification["research_queue"][0],
        qualification_task_id=qualification_task_id,
    )
    assert str(newly_retired.id) in record.terminal_reason["retired_execution_task_ids"]
    assert record.status == "needs_attention"
    assert record.next_action == next_action


def test_native_qualification_must_match_full_campaign_data_evidence():
    record = campaign()
    source = record.specification["research_queue"][0]
    binding = record.specification["dataset_bindings"][0]
    binding.update(
        {
            "catalog_digest": "1" * 64,
            "manifest_digest": "2" * 64,
            "producer_receipt_digest": "3" * 64,
            "lake_governance_digest": "4" * 64,
            "partition_digests": [binding["dataset_digest"]],
        }
    )
    expected = {
        "instrument": "BTCUSDT",
        "dataset_build_id": binding["dataset_build_id"],
        "dataset_digest": binding["dataset_digest"],
        "catalog_digest": binding["catalog_digest"],
        "manifest_digest": binding["manifest_digest"],
        "producer_receipt_digest": binding["producer_receipt_digest"],
        "lake_governance_digest": binding["lake_governance_digest"],
        "partition_digest": binding["dataset_digest"],
    }
    qualification = {
        "artifact_bundle": {
            "engine_hypothesis_yaml": {
                "immutable_contract": {"dataset_bindings": [expected]}
            }
        }
    }

    assert service._qualification_dataset_bindings_match(record, source, qualification)

    mismatched = deepcopy(qualification)
    mismatched["artifact_bundle"]["engine_hypothesis_yaml"]["immutable_contract"][
        "dataset_bindings"
    ][0]["producer_receipt_digest"] = "5" * 64
    assert not service._qualification_dataset_bindings_match(record, source, mismatched)


def test_multi_asset_qualification_requires_exact_overlap_admission():
    record = campaign()
    record.specification.update(
        execution_window_start="2025-01-01T00:00:00Z",
        execution_window_end="2026-01-01T00:00:00Z",
    )
    first = record.specification["dataset_bindings"][0]
    second = {
        **first,
        "dataset_build_id": str(uuid4()),
        "dataset_digest": "b" * 64,
        "dataset_key": "bybit-ethusdt-perp-1m",
        "instruments": ["ETHUSDT"],
    }
    record.specification["dataset_bindings"].append(second)
    source = record.specification["research_queue"][0]
    source["dataset_binding_indices"] = [0, 1]
    expected_bindings = [
        {
            "instrument": item["instruments"][0],
            "dataset_build_id": item["dataset_build_id"],
            "dataset_digest": item["dataset_digest"],
        }
        for item in (first, second)
    ]
    document = {
        "schema_version": "alpha-basket-overlap-admission-v1.0.0",
        "authority": "DATA-002/003",
        "dataset_bindings": expected_bindings,
        "instruments": ["BTCUSDT", "ETHUSDT"],
        "minimum_contiguous_days": 365,
        "admitted_start": "2025-01-01T00:00:00+00:00",
        "admitted_end": "2026-01-01T00:00:00+00:00",
    }
    receipt = {**document, "record_digest": service.digest_document(document)}

    assert not service._qualification_overlap_admission_matches(record, source, {})
    assert service._qualification_overlap_admission_matches(
        record, source, {"overlap_admission_receipt": receipt}
    )

    mutated = deepcopy(receipt)
    mutated["minimum_contiguous_days"] = 364
    mutated_document = {
        key: value for key, value in mutated.items() if key != "record_digest"
    }
    mutated["record_digest"] = service.digest_document(mutated_document)
    assert not service._qualification_overlap_admission_matches(
        record, source, {"overlap_admission_receipt": mutated}
    )

    non_utc = deepcopy(receipt)
    non_utc["admitted_start"] = "2025-01-01T01:00:00+01:00"
    non_utc_document = {
        key: value for key, value in non_utc.items() if key != "record_digest"
    }
    non_utc["record_digest"] = service.digest_document(non_utc_document)
    assert not service._qualification_overlap_admission_matches(
        record, source, {"overlap_admission_receipt": non_utc}
    )


def test_qualification_accepts_legacy_summary_result() -> None:
    legacy = {"qualified": True, "card_digest": "a" * 64}

    result = service._qualification_from_result({"summary": {"qualification": legacy}})

    assert result == legacy


def test_alpha002_materializes_one_digest_bound_vm1_task(monkeypatch):
    from app.services import retrieval

    record = campaign()
    record.specification["execution_protocol"] = "alpha002-native-v1"
    record.specification["allowed_instruments"] = ["BTCUSDT"]
    record.specification["dataset_bindings"][0].update(
        {"dataset_key": "bybit-btcusdt-perp-1m"}
    )
    db = MagicMock()
    db.scalar.return_value = None
    persisted = []
    monkeypatch.setattr(
        service,
        "_dataset_path",
        lambda *_: "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
    )
    monkeypatch.setattr(
        retrieval,
        "hybrid_search",
        lambda *_: {
            "hits": [],
            "corpus_digest": "9" * 64,
            "abstained": True,
        },
    )
    monkeypatch.setattr(
        service, "persist_new_task", lambda _db, task: persisted.append(task)
    )
    monkeypatch.setattr(service, "_append_event", MagicMock())

    task = service._ensure_execution_task(db, record)

    assert task is persisted[0]
    assert task.task_type == "alpha_research_execution"
    assert task.allowed_machines == ["vm1-developer"]
    assert task.risk_level == 0
    assert task.approval_required is False
    assert task.input_contract["campaign_digest"] == record.campaign_digest
    assert task.input_contract["authority"] == "no_capital"
    assert task.input_contract["dataset_digest"] == DIGEST


def test_alpha002_failed_execution_is_visible_as_needs_attention(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha002-native-v1"
    failed = SimpleNamespace(
        id=uuid4(),
        task_number=f"A2-{str(record.id)[:8]}-001",
        status="failed",
        failure={"reason": "native_bulletproof_failed"},
    )
    db = MagicMock()
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    monkeypatch.setattr(service, "_ensure_execution_task", lambda *_: failed)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.reconcile_campaign(db, record)

    assert record.status == "needs_attention"
    assert record.terminal_reason["task_id"] == str(failed.id)


def test_alpha002_cancellation_propagates_to_queued_execution(monkeypatch):
    record = campaign()
    task = SimpleNamespace(
        id=uuid4(),
        status="queued",
        completed_at=None,
        cancel_requested_at=None,
        cancel_reason=None,
    )
    db = MagicMock()
    db.scalar.return_value = task
    append = MagicMock()
    monkeypatch.setattr("app.services.tasks.append_task_event", append)
    monkeypatch.setattr("app.services.tasks.clear_lease", MagicMock())
    monkeypatch.setattr(
        "app.services.agent_context.discard_working_memory", MagicMock()
    )
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.cancel_campaign(
        db,
        record,
        service.AlphaCampaignAction(
            expected_campaign_digest=DIGEST,
            actor="founder-operator",
            reason="Stop this bounded campaign immediately.",
        ),
    )

    assert task.status == "cancelled"
    assert task.cancel_requested_at is not None
    append.assert_called_once()


def test_needs_attention_campaign_can_be_cancelled_after_failed_recovery(monkeypatch):
    record = campaign(status="needs_attention")
    record.terminal_reason = {"category": "governed_pipeline_task_failed"}
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.cancel_campaign(
        db,
        record,
        service.AlphaCampaignAction(
            expected_campaign_digest=DIGEST,
            actor="founder-operator",
            reason="Retain the failed recovery and continue autonomous discovery.",
        ),
    )

    assert record.status == "cancelled"
    assert record.terminal_reason["category"] == "operator_cancelled"


@pytest.mark.parametrize(
    "status", ["cancelled", "completed_no_candidate", "shadow_candidate"]
)
def test_completed_campaigns_cannot_be_cancelled_again(status):
    record = campaign(status=status)
    with pytest.raises(HTTPException, match="Terminal campaigns"):
        service.cancel_campaign(
            MagicMock(),
            record,
            service.AlphaCampaignAction(
                expected_campaign_digest=DIGEST,
                actor="founder-operator",
                reason="This cancellation must remain forbidden.",
            ),
        )


def attempt(record, **updates):
    question = "Does lagged BTC displacement retain net predictive value after costs?"
    value = {
        "attempt_key": "attempt-1",
        "expected_campaign_digest": DIGEST,
        "question": question,
        "question_digest": service.digest_document({"question": question}),
        "source_candidate_id": record.specification["research_queue"][0][
            "source_candidate_id"
        ],
        "source_candidate_digest": record.specification["research_queue"][0][
            "source_candidate_digest"
        ],
        "hypothesis_id": "ALPHA001-H1",
        "hypothesis_digest": "2" * 64,
        "dataset_build_id": record.specification["dataset_bindings"][0][
            "dataset_build_id"
        ],
        "dataset_digest": DIGEST,
        "trial_count": 4,
        "outcome": "negative",
        "failure_stage": None,
        "gate_report": {
            "truth_certified": True,
            "point_in_time_valid": True,
            "reproducible": True,
            "out_of_sample_evaluated": True,
            "cost_stress_evaluated": True,
            "selection_bias_audited": True,
            "independent_review_complete": True,
            "shadow_eligible": False,
            "failed_gates": ["minimum_out_of_sample_evidence"],
        },
        "evidence_digests": ["3" * 64],
        "produced_by": "bulletproof_bt",
        "source_commit": COMMIT,
    }
    value.update(updates)
    return AlphaCampaignAttemptCreate.model_validate(value)


def test_contract_has_no_capital_or_order_authority():
    payload = request()
    assert payload.authority == "no_capital"
    assert (
        payload.may_self_approve
        is payload.may_place_orders
        is payload.may_promote_live
        is False
    )


def test_attempt_accepts_native_execution_scope_and_logging_evidence():
    record = campaign()
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "execution_class": "qualification",
            "qualification_authority": True,
            "required_trade_logging_complete": True,
        }
    )

    payload = attempt(record, gate_report=gate_report)

    assert payload.gate_report.execution_class == "qualification"
    assert payload.gate_report.qualification_authority is True
    assert payload.gate_report.required_trade_logging_complete is True


def test_commissioning_attempt_cannot_claim_qualification_authority():
    record = campaign()
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "execution_class": "commissioning",
            "qualification_authority": True,
            "required_trade_logging_complete": True,
        }
    )

    with pytest.raises(ValidationError, match="cannot have qualification authority"):
        attempt(record, gate_report=gate_report)


def test_candidate_requires_complete_no_capital_gates():
    with pytest.raises(ValidationError, match="candidate"):
        AlphaCampaignAttemptCreate.model_validate(
            attempt(campaign()).model_dump() | {"outcome": "candidate"}
        )


def test_positive_scientific_result_is_retained_without_shadow_admission():
    record = campaign()
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "required_trade_logging_complete": True,
            "execution_class": "qualification",
            "qualification_authority": True,
            "failed_gates": [],
        }
    )
    payload = attempt(record, outcome="positive", gate_report=gate_report)

    assert payload.outcome == "positive"
    assert payload.gate_report.shadow_eligible is False


def test_positive_scientific_result_rejects_failed_or_commissioning_gates():
    record = campaign()
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "required_trade_logging_complete": True,
            "execution_class": "qualification",
            "qualification_authority": True,
            "failed_gates": [],
        }
    )
    for update in (
        {"truth_certified": False},
        {"cost_stress_evaluated": False},
        {"required_trade_logging_complete": False},
        {"failed_gates": ["scientific_gate"]},
        {"shadow_eligible": True},
        {"execution_class": "commissioning", "qualification_authority": False},
    ):
        with pytest.raises(ValidationError, match="positive scientific outcomes"):
            attempt(
                record,
                outcome="positive",
                gate_report=gate_report | update,
            )


def test_registration_admits_real_exchange_lineage():
    payload = request()
    record = service.register_campaign(database(payload), payload)
    assert record.status == "awaiting_activation"
    assert record.specification["dataset_bindings"][0]["venue"] == "bybit"
    assert record.specification["dataset_bindings"][0]["output_columns"] == [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
    ]
    assert record.specification["authority_boundary"]["capital"] is False
    assert "execution_protocol" not in record.specification
    assert record.specification["research_queue"][0]["resampling_policy"] == (
        "left_closed_left_labeled_complete_bars"
    )


def test_alpha002_opt_in_is_immutable_and_explicit():
    payload = request(execution_protocol="alpha002-native-v1")
    record = service.register_campaign(database(payload), payload)
    assert record.specification["execution_protocol"] == "alpha002-native-v1"


def test_alpha003_requires_an_immutable_execution_window():
    with pytest.raises(ValidationError, match="immutable execution window"):
        request(execution_protocol="alpha003-governed-v1")
    payload = request(
        execution_protocol="alpha003-governed-v1",
        execution_window_start="2026-04-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
    )
    assert payload.execution_window_start < payload.execution_window_end


def test_alpha003_stage_contract_binds_data_window_and_research_context(monkeypatch):
    record = campaign()
    record.specification.update(
        {
            "execution_protocol": "alpha003-governed-v1",
            "allowed_instruments": ["BTCUSDT"],
            "execution_window_start": "2026-04-01T00:00:00Z",
            "execution_window_end": "2026-05-01T00:00:00Z",
        }
    )
    record.specification["dataset_bindings"][0].update(
        {
            "dataset_key": "bybit-btcusdt-perp-1m",
            "venue": "bybit",
            "catalog_digest": "1" * 64,
            "manifest_digest": "2" * 64,
            "producer_receipt_digest": "3" * 64,
            "lake_governance_digest": "4" * 64,
            "partition_digests": [DIGEST],
        }
    )
    capability = {
        "hypothesis_id": "ALPHA-WEEKEND-MOMENTUM",
        "title": "Weekend lagged-return momentum",
        "description": "Tests lagged weekend momentum on held-out data.",
        "hypothesis_family": "lagged-return-momentum",
        "strategy": "alpha_weekend_momentum",
        "input_mode": "single_instrument",
        "maximum_instruments": 1,
        "signal_timeframes": ["1m"],
        "variant_count": 8,
        "logging_requirements": ["decision_trace", "stop_price"],
        "reuse_blockers": [],
        "bounded_weekly_reuse_eligible": True,
        "contract_path": "research/hypotheses/alpha_weekend_momentum.yaml",
        "contract_digest": "8" * 64,
    }
    record.specification["research_queue"][0]["reusable_strategy"] = capability
    monkeypatch.setattr(
        service,
        "_dataset_path",
        lambda *_: "/home/omenka/Projects/bulletproof_bt/research_data/panel.parquet",
    )
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "abstained": False, "citations": []},
    )
    contract = service._stage_contract(
        MagicMock(), record, record.specification["research_queue"][0], stage="draft"
    )
    assert contract["stage"] == "draft"
    assert contract["venue"] == "bybit"
    assert contract["window_start"] == "2026-04-01T00:00:00Z"
    assert contract["dataset_digest"] == DIGEST
    assert contract["reusable_strategy"] == capability
    assert contract["dataset_bindings"][0]["catalog_digest"] == "1" * 64
    assert contract["dataset_bindings"][0]["manifest_digest"] == "2" * 64
    assert contract["dataset_bindings"][0]["producer_receipt_digest"] == "3" * 64
    assert contract["dataset_bindings"][0]["lake_governance_digest"] == "4" * 64
    assert contract["dataset_bindings"][0]["partition_digest"] == DIGEST


def test_stage_contract_canonicalizes_legacy_resampling_policy(monkeypatch):
    record = campaign()
    record.specification.update(
        {
            "execution_protocol": "alpha003-governed-v1",
            "allowed_instruments": ["BTCUSDT"],
            "execution_window_start": "2026-04-01T00:00:00Z",
            "execution_window_end": "2026-05-01T00:00:00Z",
        }
    )
    source = record.specification["research_queue"][0]
    source["resampling_policy"] = "right_closed_left_labeled_complete_bars"
    monkeypatch.setattr(service, "_dataset_path", lambda *_: "/tmp/panel.parquet")
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "abstained": False, "citations": []},
    )

    contract = service._stage_contract(MagicMock(), record, source, stage="draft")

    assert contract["resampling_policy"] == "left_closed_left_labeled_complete_bars"


def test_unknown_resampling_policy_is_rejected_before_task_creation():
    with pytest.raises(HTTPException, match="Unsupported research resampling policy"):
        service._canonical_resampling_policy({"resampling_policy": "ambiguous-bars"})


def test_governed_pipeline_clears_prior_stage_reason(monkeypatch):
    record = campaign()
    record.specification.update(
        {
            "execution_protocol": "alpha003-governed-v1",
            "allowed_instruments": ["BTCUSDT"],
            "execution_window_start": "2026-04-01T00:00:00Z",
            "execution_window_end": "2026-05-01T00:00:00Z",
        }
    )
    record.terminal_reason = {"category": "independent_strategy_review_pending"}
    task = SimpleNamespace(status="queued")
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_stage_contract", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_create_stage_task", lambda *_args, **_kwargs: task)

    assert service._advance_governed_pipeline(db, record) is task
    assert record.phase == "hypothesis_draft"
    assert record.terminal_reason == {}


def test_running_strategy_engineering_is_not_terminalized(monkeypatch):
    record = campaign(status="needs_attention")
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    engineering = SimpleNamespace(id=uuid4(), status="running", result={})
    db = MagicMock()
    db.scalar.side_effect = [draft, engineering]

    assert service._advance_governed_pipeline(db, record) is engineering
    assert record.status == "running"
    assert record.phase == "strategy_engineering"
    assert record.next_action == "await_bounded_strategy_engineering"
    assert record.terminal_reason == {}


def test_reconciliation_recovers_requeued_strategy_engineering(monkeypatch):
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="strategy_engineering",
        next_action="strategy_engineering_failed",
        completed_at=datetime.now(UTC),
        terminal_reason={
            "category": "strategy_engineering_failed",
            "task_id": str(task_id),
            "status": "running",
        },
    )
    engineering = SimpleNamespace(id=task_id, status="pending_approval")
    db = MagicMock()
    db.get.return_value = engineering
    advance = MagicMock(return_value=engineering)
    monkeypatch.setattr(service, "_advance_governed_pipeline", advance)
    record.specification["execution_protocol"] = "alpha003-governed-v1"

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.completed_at is None
    assert record.terminal_reason == {}
    advance.assert_called_once_with(db, record)


def test_reconciliation_recovers_review_rejection_into_correction(monkeypatch):
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="complete",
        next_action="operator_review",
        completed_at=datetime.now(UTC),
        terminal_reason={
            "category": "governed_pipeline_task_failed",
            "task_id": str(task_id),
        },
    )
    rejected = SimpleNamespace(id=task_id)
    correction = {"findings": [{"severity": "high", "message": "fix causality"}]}
    db = MagicMock()
    db.get.return_value = rejected
    advance = MagicMock(return_value=SimpleNamespace(status="pending_approval"))
    monkeypatch.setattr(service, "_independent_review_correction", lambda _: correction)
    monkeypatch.setattr(service, "_advance_governed_pipeline", advance)
    monkeypatch.setattr(service, "_append_event", MagicMock())
    record.specification["execution_protocol"] = "alpha003-governed-v1"

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.completed_at is None
    assert record.terminal_reason == {}
    advance.assert_called_once_with(db, record)


def test_reconciliation_recovers_strategy_engineering_rejection_into_correction(
    monkeypatch,
):
    task_id = uuid4()
    record = campaign(
        status="needs_attention",
        phase="strategy_engineering",
        next_action="strategy_engineering_failed",
        completed_at=datetime.now(UTC),
        terminal_reason={
            "category": "strategy_engineering_failed",
            "task_id": str(task_id),
            "status": "leased",
            "result": {},
        },
    )
    rejected = SimpleNamespace(id=task_id, status="failed")
    correction = {"findings": [{"severity": "high", "message": "fix causality"}]}
    db = MagicMock()
    db.get.return_value = rejected
    advance = MagicMock(return_value=SimpleNamespace(status="pending_approval"))
    monkeypatch.setattr(service, "_independent_review_correction", lambda _: correction)
    monkeypatch.setattr(service, "_advance_governed_pipeline", advance)
    monkeypatch.setattr(service, "_append_event", MagicMock())
    record.specification["execution_protocol"] = "alpha003-governed-v1"

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.phase == "strategy_engineering"
    assert record.next_action == "create_review_bound_strategy_correction"
    assert record.completed_at is None
    assert record.terminal_reason == {}
    advance.assert_called_once_with(db, record)


@pytest.mark.parametrize(
    "mutation",
    [None, "claim", "dataset", "window", "digest", "provenance", "overlap"],
)
def test_alpha003_compiler_boolean_cannot_authorize_execution(monkeypatch, mutation):
    record = campaign()
    binding = record.specification["dataset_bindings"][0]
    binding.update(
        {
            "catalog_digest": "1" * 64,
            "manifest_digest": "2" * 64,
            "producer_receipt_digest": "3" * 64,
            "lake_governance_digest": "4" * 64,
            "partition_digests": [binding["dataset_digest"]],
        }
    )
    frozen = {
        "dataset_build_id": str(uuid4()),
        "dataset_digest": DIGEST,
        "venue": "bybit",
        "instrument": "BTCUSDT",
        "timeframe": "1m",
        "window_start": "2025-01-01T00:00:00Z",
        "window_end": "2026-01-01T00:00:00Z",
    }
    dataset = {
        key: frozen[key]
        for key in (
            "dataset_build_id",
            "dataset_digest",
            "venue",
            "instrument",
            "timeframe",
        )
    }
    window = {"start": frozen["window_start"], "end": frozen["window_end"]}
    card = {
        "status": "draft",
        "research_question": record.specification["research_queue"][0]["question"],
        "dataset_binding": dataset,
        "execution_window": window,
        "parameters": {"lookback": [60]},
    }
    draft = SimpleNamespace(
        assigned_agent_id=uuid4(),
        status="succeeded",
        result={"summary": {"hypothesis_card": card}},
    )
    confirmation = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "approved_by": "founder-operator",
                "approved_at": datetime.now(UTC).isoformat(),
                "plan_digest": DIGEST,
            }
        },
    )
    confirmed = deepcopy(card)
    confirmed.update(
        {
            "status": "confirmed",
            "confirmed_by": "founder-operator",
            "confirmed_at": confirmation.result["summary"]["approved_at"],
        }
    )
    qualification = SimpleNamespace(
        id=uuid4(),
        assigned_agent_id=uuid4(),
        status="succeeded",
        input_contract=frozen,
        result={
            "summary": {
                "qualification": {
                    "qualified": True,
                    "card": confirmed,
                    "card_digest": service.digest_document(confirmed),
                    "dataset": dataset,
                    "window": window,
                    "parameter_grid": card["parameters"],
                    "artifact_bundle": {"technical": "ready"},
                    "review": {"independent_of_drafter": True},
                }
            }
        },
    )
    db = MagicMock()
    result = qualification.result["summary"]["qualification"]
    if mutation == "claim":
        result["card"]["claim"] = "A substituted hypothesis"
    elif mutation == "dataset":
        result["card"]["dataset_binding"]["dataset_digest"] = "c" * 64
    elif mutation == "window":
        result["card"]["execution_window"]["end"] = "2027-01-01T00:00:00Z"
    elif mutation == "digest":
        result["card_digest"] = "c" * 64
    elif mutation == "provenance":
        result["artifact_bundle"] = {
            "engine_hypothesis_yaml": {
                "immutable_contract": {
                    "dataset_bindings": [
                        {
                            "instrument": "BTCUSDT",
                            "dataset_build_id": binding["dataset_build_id"],
                            "dataset_digest": binding["dataset_digest"],
                            "catalog_digest": binding["catalog_digest"],
                            "manifest_digest": binding["manifest_digest"],
                            "producer_receipt_digest": "5" * 64,
                            "lake_governance_digest": binding["lake_governance_digest"],
                            "partition_digest": binding["dataset_digest"],
                        }
                    ]
                }
            }
        }
    elif mutation == "overlap":
        second = {
            **binding,
            "dataset_build_id": str(uuid4()),
            "dataset_digest": "b" * 64,
            "dataset_key": "bybit-ethusdt-perp-1m",
            "instruments": ["ETHUSDT"],
            "partition_digests": ["b" * 64],
        }
        record.specification["dataset_bindings"].append(second)
        record.specification["research_queue"][0]["dataset_binding_indices"] = [
            0,
            1,
        ]
    db.scalar.side_effect = [draft, confirmation, qualification, None, None]
    create = MagicMock()
    monkeypatch.setattr(service, "_create_stage_task", create)
    monkeypatch.setattr(
        service,
        "task_producer_identity",
        lambda db, task: {
            "agent_id": str(
                draft.assigned_agent_id
                if task is draft
                else qualification.assigned_agent_id
            ),
            "context_group": "compiler-test",
            "package_digest": "d" * 64,
            "machine": "vm1",
            "provider": "deterministic",
            "model_family": "none",
            "runtime": "python",
        },
    )
    route_create = MagicMock(
        side_effect=lambda db, payload: SimpleNamespace(
            id=uuid4(),
            subject_type=payload.subject_type,
            subject_digest=payload.subject_digest,
            status="blocked",
            blocked_reason={"category": "independent_evaluator_unavailable"},
        )
    )
    monkeypatch.setattr(service, "create_route", route_create)
    assert service._advance_governed_pipeline(db, record) is qualification
    if mutation == "provenance":
        assert record.status == "needs_attention"
        assert record.next_action == "rebind_native_strategy_to_admitted_data_evidence"
        assert record.terminal_reason == {
            "category": "qualification_dataset_binding_mismatch",
            "qualification_task_id": str(qualification.id),
            "retired_execution_task_ids": [],
        }
        create.assert_not_called()
        route_create.assert_not_called()
        return
    if mutation == "overlap":
        assert record.status == "needs_attention"
        assert record.next_action == "requalify_native_strategy_with_overlap_admission"
        assert record.terminal_reason == {
            "category": "qualification_overlap_admission_missing_or_invalid",
            "qualification_task_id": str(qualification.id),
            "retired_execution_task_ids": [],
        }
        create.assert_not_called()
        route_create.assert_not_called()
        return
    if mutation:
        assert record.status == "needs_attention"
        assert record.next_action == "repair_qualification_approval_binding"
        create.assert_not_called()
        route_create.assert_not_called()
        return
    assert record.phase == "independent_strategy_review"
    assert record.next_action == "route_independent_strategy_review"
    assert record.terminal_reason["subject"]["source_commit"] == COMMIT
    assert len(record.terminal_reason["subject_digest"]) == 64
    route_create.assert_called_once()
    routing = route_create.call_args.args[1]
    assert len(routing.excluded_producers) == 2
    assert routing.producer.agent_id == qualification.assigned_agent_id
    assert record.terminal_reason["route_status"] == "blocked"
    create.assert_not_called()


def test_routed_review_tasks_preserve_subject_profile_and_source_without_execution(
    monkeypatch,
):
    assignment = SimpleNamespace(
        id=uuid4(), evaluator_profile_id=uuid4(), review_kind="strategy_spec"
    )
    profile = SimpleNamespace(
        agent_id=uuid4(),
        machine="vm1-developer",
        profile_digest="b" * 64,
        package_digest="c" * 64,
    )
    route = SimpleNamespace(id=uuid4(), status="assigned", subject_digest=DIGEST)
    subject = {"source_commit": COMMIT, "card_digest": "d" * 64}
    qualification = {
        "card": {"status": "confirmed"},
        "artifact_bundle": {"strategy_spec": "exact"},
    }
    db = MagicMock()
    db.scalars.return_value.all.return_value = [assignment]
    db.get.return_value = profile
    db.scalar.return_value = None
    build = MagicMock(return_value=SimpleNamespace(id=uuid4()))
    persist = MagicMock()
    monkeypatch.setattr(service, "build_task", build)
    monkeypatch.setattr(service, "persist_new_task", persist)
    service._materialize_strategy_review_tasks(db, route, subject, qualification)
    payload = build.call_args.args[0]
    assert payload.task_type == "alpha_strategy_review"
    assert payload.required_capabilities == ["alpha-strategy-review-strategy_spec"]
    assert payload.input_contract["base_ref"] == COMMIT
    assert payload.input_contract["evaluator_agent_id"] == str(profile.agent_id)
    assert payload.input_contract["evaluator_package_digest"] == profile.package_digest
    assert payload.input_contract["qualification"] == qualification
    assert payload.input_contract["authority"] == "review_only_no_execution"
    persist.assert_called_once()
    db.scalar.return_value = SimpleNamespace(id=uuid4())
    service._materialize_strategy_review_tasks(db, route, subject, qualification)
    assert persist.call_count == 1
    route.status = "blocked"
    service._materialize_strategy_review_tasks(db, route, subject, qualification)
    assert persist.call_count == 1


def test_stale_reviewer_route_is_retained_and_superseded(monkeypatch):
    assignment = SimpleNamespace(
        id=uuid4(),
        evaluator_profile_id=uuid4(),
        review_kind="strategy_spec",
        status="assigned",
        completed_at=None,
    )
    profile = SimpleNamespace(
        agent_id=uuid4(),
        status="active",
        machine="vm1-developer",
        runtime="unknown",
    )
    agent = SimpleNamespace(
        is_enabled=True,
        machine="vm1-developer",
        runtime="hermes",
        runtime_version="0.3.2",
    )
    route = SimpleNamespace(
        id=uuid4(),
        status="assigned",
        subject_type="alpha_strategy_qualification",
        subject_id=str(uuid4()),
        subject_digest=DIGEST,
        requested_by="alpha-campaign-director",
        completed_at=None,
        blocked_reason={},
        policy={
            "required_review_kinds": ["strategy_spec"],
            "required_capabilities": [],
            "max_pairwise_shared_dimensions": 4,
            "routing_revision": 1,
        },
    )
    task = SimpleNamespace(
        status="running",
        failure={},
        completed_at=None,
        assigned_agent_id=profile.agent_id,
    )
    identities = [
        {
            "agent_id": str(uuid4()),
            "machine": "vm1-developer",
            "provider": "openai",
            "model_family": "codex",
            "runtime": "hermes/0.3.2",
            "context_group": f"producer-{position}",
            "package_digest": str(position) * 64,
            "profile_digest": str(position + 2) * 64,
        }
        for position in (1, 2)
    ]
    db = MagicMock()
    db.scalars.return_value.all.return_value = [assignment]

    def get(_model, identifier):
        if identifier == assignment.evaluator_profile_id:
            return profile
        if identifier == profile.agent_id:
            return agent
        return None

    db.get.side_effect = get
    db.scalar.return_value = task
    successor = SimpleNamespace(id=uuid4(), status="blocked")
    create = MagicMock(return_value=successor)
    event = MagicMock()
    task_event = MagicMock()
    clear = MagicMock()
    monkeypatch.setattr(service, "create_route", create)
    monkeypatch.setattr(service, "append_evaluation_event", event)
    monkeypatch.setattr(service, "append_task_event", task_event)
    monkeypatch.setattr(service, "clear_lease", clear)

    result = service._supersede_stale_strategy_review_route(
        db, route, {"producer_identities": identities}
    )

    assert result is successor
    assert route.status == "superseded"
    assert route.blocked_reason["category"] == "stale_evaluator_profile"
    assert assignment.status == "superseded"
    assert task.status == "failed"
    assert task.failure["category"] == "stale_evaluator_profile"
    clear.assert_called_once_with(task)
    payload = create.call_args.args[1]
    assert payload.routing_revision == 2
    assert payload.supersedes_route_id == route.id


def test_failed_strategy_review_task_supersedes_route_without_a_verdict(monkeypatch):
    assignment = SimpleNamespace(
        id=uuid4(), status="assigned", review_id=None, completed_at=None
    )
    route = SimpleNamespace(
        id=uuid4(),
        status="assigned",
        subject_type="alpha_strategy_qualification",
        subject_id=str(uuid4()),
        subject_digest="a" * 64,
        requested_by="alpha-campaign-director",
        completed_at=None,
        blocked_reason={},
        policy={
            "required_review_kinds": ["strategy_spec", "causality_leakage"],
            "required_capabilities": [],
            "max_pairwise_shared_dimensions": 4,
            "routing_revision": 2,
        },
    )
    task = SimpleNamespace(
        id=uuid4(),
        status="failed",
        failure={"retryable": True},
    )
    identities = [
        {
            "agent_id": str(uuid4()),
            "machine": "vm1-developer",
            "provider": "openai",
            "model_family": "codex",
            "runtime": "hermes/0.3.2",
            "context_group": f"producer-{position}",
            "package_digest": str(position) * 64,
            "profile_digest": str(position + 2) * 64,
        }
        for position in (1, 2)
    ]
    db = MagicMock()
    db.scalars.return_value.all.return_value = [assignment]
    db.scalar.return_value = task
    successor = SimpleNamespace(id=uuid4(), status="assigned")
    create = MagicMock(return_value=successor)
    event = MagicMock()
    monkeypatch.setattr(service, "create_route", create)
    monkeypatch.setattr(service, "append_evaluation_event", event)

    result = service._supersede_failed_strategy_review_route(
        db, route, {"producer_identities": identities}
    )

    assert result is successor
    assert route.status == "superseded"
    assert route.blocked_reason["category"] == (
        "reviewer_task_exhausted_without_verdict"
    )
    assert assignment.status == "superseded"
    payload = create.call_args.args[1]
    assert payload.routing_revision == 3
    assert payload.supersedes_route_id == route.id


def test_strategy_review_rejection_is_retained_as_invalid_without_trials(monkeypatch):
    source = {
        "source_candidate_id": str(uuid4()),
        "source_candidate_digest": "1" * 64,
        "question": "Does the exact causal signal predict the next return?",
    }
    campaign = SimpleNamespace(
        campaign_digest="2" * 64,
        specification={
            "bulletproof_source_commit": COMMIT,
            "dataset_bindings": [
                {
                    "dataset_build_id": str(uuid4()),
                    "dataset_digest": "3" * 64,
                }
            ],
        },
    )
    qualification = {
        "card_digest": "7" * 64,
        "artifact_bundle": {
            "engine_hypothesis_yaml": {
                "hypothesis_id": "CAUSAL-H1",
                "generation_provenance": {"source_card_hash": "7" * 64},
            }
        },
    }
    route = SimpleNamespace(id=uuid4(), route_digest="4" * 64)
    reviews = [
        SimpleNamespace(blockers=["60-minute target differs from a 240-minute hold"])
    ]
    assignments = [SimpleNamespace(review_digest="5" * 64)]
    db = MagicMock()
    db.scalars.return_value.all.return_value = assignments
    monkeypatch.setattr(
        service,
        "require_independence",
        lambda db, route: SimpleNamespace(receipt_digest="6" * 64),
    )
    retained = MagicMock()
    monkeypatch.setattr(service, "record_attempt", retained)

    service._retain_strategy_review_rejection(
        db, campaign, source, qualification, route, reviews
    )

    payload = retained.call_args.args[2]
    assert payload.outcome == "invalid"
    assert payload.trial_count == 0
    assert payload.gate_report.independent_review_complete is True
    assert payload.gate_report.shadow_eligible is False
    assert payload.evidence_digests == ["4" * 64, "5" * 64, "6" * 64]


def test_rejected_strategy_requires_hypothesis_bound_to_approved_card():
    source = {
        "source_candidate_id": str(uuid4()),
        "source_candidate_digest": "1" * 64,
        "question": "Does the exact causal signal predict the next return?",
    }
    campaign = SimpleNamespace(
        campaign_digest="2" * 64,
        specification={
            "bulletproof_source_commit": COMMIT,
            "dataset_bindings": [
                {
                    "dataset_build_id": str(uuid4()),
                    "dataset_digest": "3" * 64,
                }
            ],
        },
    )
    qualification = {
        "card_digest": "7" * 64,
        "artifact_bundle": {
            "engine_hypothesis_yaml": {
                "hypothesis_id": "CAUSAL-H1",
                "generation_provenance": {"source_card_hash": "8" * 64},
            }
        },
    }

    with pytest.raises(HTTPException, match="immutable hypothesis contract"):
        service._retain_strategy_review_rejection(
            MagicMock(),
            campaign,
            source,
            qualification,
            SimpleNamespace(id=uuid4(), route_digest="4" * 64),
            [SimpleNamespace(blockers=["semantic mismatch"])],
        )


def test_alpha003_strategy_gap_materializes_approval_gated_bulletproof_engineering(
    monkeypatch,
):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.specification.update(
        allowed_instruments=["ETHUSDT"],
        execution_window_start="2025-05-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
        authority_boundary={
            "capital": False,
            "orders": False,
            "production_promotion": False,
            "self_approval": False,
        },
    )
    source = record.specification["research_queue"][0]
    source["discovery_candidate_id"] = str(uuid4())
    source["discovery_candidate_digest"] = "7" * 64
    source_document = {"predictor": "lagged displacement", "target": "next-hour return"}
    db = MagicMock()
    db.scalar.return_value = None
    db.get.return_value = SimpleNamespace(
        candidate_digest="7" * 64,
        question=source["question"],
        document=source_document,
    )
    persisted = []
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "citations": []},
    )
    monkeypatch.setattr(
        service, "persist_new_task", lambda _db, task: persisted.append(task)
    )

    task = service._create_strategy_engineering_task(
        db,
        record,
        source,
        {"category": "exact_strategy_unavailable"},
    )

    assert task is persisted[0]
    assert task.project == "bulletproof_bt"
    assert task.task_type == "engineering_mission"
    assert task.approval_required is False
    assert task.status == "queued"
    assert task.approval_policy["kind"] == "bounded_hypothesis_engineering"
    assert task.approval_policy["founder_approval_exempt"] is True
    assert task.required_capabilities == [
        "alpha-strategy-engineering",
        "git",
        "python",
        "testing",
    ]
    assert not set(task.required_capabilities).issubset({"git", "python", "testing"})
    assert task.input_contract["allowed_paths"] == [
        "research/hypotheses",
        "src/bt/strategy",
        "docs/hypotheses",
        "tests",
        "src/bt/governance/alpha_strategy_pipeline.py",
        "scripts/run_alpha_research_assignment.py",
    ]
    assert task.task_number.endswith("-G3")
    assert task.input_contract["context_paths"] == [
        "docs/hypothesis_strategy_generation_prompt_instructions.md",
        "docs/backtest_truth_certification.md",
        "docs/timeframe_resampler.md",
        "src/bt/governance/alpha_strategy_pipeline.py",
        "scripts/run_alpha_research_assignment.py",
    ]
    assert task.input_contract["base_ref"] == COMMIT
    import json

    evidence = json.loads(task.input_contract["evidence_context"])
    assert evidence["question"] == source["question"]
    assert evidence["dataset_binding"] == record.specification["dataset_bindings"][0]
    assert evidence["maximum_variants"] == 8
    assert evidence["research_context"]["corpus_digest"] == "9" * 64
    assert evidence["discovery_candidate"] == source_document
    assert not evidence["authority"]["capital"]
    db.get.return_value.candidate_digest = "8" * 64
    with pytest.raises(HTTPException, match="absent or changed"):
        service._create_strategy_engineering_task(db, record, source, {})
    db.get.return_value.candidate_digest = "7" * 64
    db.get.return_value.question = "Does a different signal predict a different target?"
    with pytest.raises(HTTPException, match="absent or changed"):
        service._create_strategy_engineering_task(db, record, source, {})
    assert len(persisted) == 1

    for bad_evidence in (
        "[]",
        "not-json",
        '{"x": NaN}',
        '{"x":' + "[" * 1500 + "0" + "]" * 1500 + "}",
        json.dumps({"text": "x" * 48001}),
    ):
        document = dict(task.input_contract, evidence_context=bad_evidence)
        with pytest.raises(ValidationError):
            ProposalEngineeringMissionContract.model_validate(document)


def test_legacy_strategy_engineering_approval_is_narrowly_waived(monkeypatch):
    task = SimpleNamespace(
        id=uuid4(),
        project="bulletproof_bt",
        task_type="engineering_mission",
        created_by="alpha-campaign-director",
        risk_level=1,
        required_capabilities=["alpha-strategy-engineering", "git", "python"],
        input_contract={
            "workflow": "engineering-mission",
            "milestone_id": "ALPHA-003",
            "allowed_paths": list(service.STRATEGY_ENGINEERING_ALLOWED_PATHS),
            "evidence_context": json.dumps(
                {
                    "authority": {
                        "capital": False,
                        "orders": False,
                        "production_promotion": False,
                        "self_approval": False,
                    }
                }
            ),
        },
        approval_required=True,
        status="pending_approval",
        approval_policy={"kind": "explicit"},
        plan_digest="1" * 64,
        attempt_count=0,
    )
    approval = SimpleNamespace(
        id=uuid4(),
        status="pending",
        decided_by=None,
        decision_reason=None,
        updated_at=None,
    )
    notification = SimpleNamespace(state="pending", superseded_at=None, updated_at=None)
    db = MagicMock()
    db.scalar.return_value = approval
    db.scalars.return_value.all.return_value = [notification]
    approval_events = []
    task_events = []
    monkeypatch.setattr(
        service,
        "append_approval_event",
        lambda *args, **kwargs: approval_events.append((args, kwargs)),
    )
    monkeypatch.setattr(
        service,
        "append_task_event",
        lambda *args, **kwargs: task_events.append((args, kwargs)),
    )

    assert service._release_legacy_hypothesis_engineering_approval(db, task)
    assert task.status == "queued"
    assert task.approval_required is False
    assert task.approval_policy["kind"] == "bounded_hypothesis_engineering"
    assert approval.status == "revoked"
    assert notification.state == "superseded"
    assert approval_events[0][0][2] == "approval_requirement_waived"
    assert task_events[0][0][2] == "approval_requirement_waived"


def test_strategy_engineering_waiver_rejects_external_engineering():
    task = SimpleNamespace(
        approval_required=True,
        status="pending_approval",
        project="bulletproof_bt",
        task_type="engineering_mission",
        created_by="founder-planner",
        risk_level=1,
        required_capabilities=["git", "python"],
        input_contract={
            "workflow": "engineering-mission",
            "milestone_id": "OTHER",
            "allowed_paths": ["src"],
            "evidence_context": "{}",
        },
    )

    assert not service._release_legacy_hypothesis_engineering_approval(
        MagicMock(), task
    )


def test_independent_review_failure_materializes_new_correction_task(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G3",
        status="failed",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        result={},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json", "artifacts/changes.patch"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "causal mismatch",
                        "findings": [
                            {
                                "severity": "high",
                                "message": "matched controls are absent",
                            }
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    corrected = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=corrected)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    result = service._advance_governed_pipeline(db, record)

    assert result is corrected
    assert record.phase == "strategy_engineering"
    assert record.next_action == "founder_strategy_engineering_approval"
    kwargs = create.call_args.kwargs
    assert kwargs["stage"] == "G4"
    assert kwargs["parent_task_id"] == rejected.id
    assert kwargs["correction_feedback"]["cumulative_findings"][0]["severity"] == "high"


def test_strategy_correction_evidence_stays_within_typed_contract(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.specification.update(
        allowed_instruments=["BTCUSDT"],
        execution_window_start="2025-05-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
        authority_boundary={
            "capital": False,
            "orders": False,
            "production_promotion": False,
            "self_approval": False,
        },
    )
    source = record.specification["research_queue"][0]
    source["instrument"] = "BTCUSDT"
    source["discovery_candidate_id"] = str(uuid4())
    source["discovery_candidate_digest"] = "7" * 64
    db = MagicMock()
    db.scalar.return_value = None
    db.get.return_value = SimpleNamespace(
        candidate_digest="7" * 64,
        question=source["question"],
        document={"predictor": "lagged displacement", "target": "next-hour return"},
    )
    persisted = []
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "citations": []},
    )
    monkeypatch.setattr(
        service, "persist_new_task", lambda _db, task: persisted.append(task)
    )
    correction = {
        "rejected_task_id": str(uuid4()),
        "rejected_plan_digest": "a" * 64,
        "review_summary": "The implementation needs scientific correction.",
        "latest_findings": [
            {"severity": "high", "message": "held-out evaluation is absent"}
        ],
        "cumulative_findings": [
            {"severity": "high", "message": "held-out evaluation is absent"}
        ],
        "artifact_paths": ["artifacts/review.json", "artifacts/changes.patch"],
        "disposition": "correct_without_weakening_scientific_gates",
    }

    task = service._create_strategy_engineering_task(
        db,
        record,
        source,
        {"category": "exact_strategy_unavailable"},
        stage="G4",
        correction_feedback=correction,
        parent_task_id=uuid4(),
    )

    evidence = json.loads(task.input_contract["evidence_context"])
    assert task is persisted[0]
    assert "dataset_binding" not in evidence
    assert evidence["dataset_bindings"] == record.specification["dataset_bindings"]
    assert evidence["independent_review_correction"] == correction
    assert len(evidence) <= 20
    ProposalEngineeringMissionContract.model_validate(task.input_contract)


def test_strategy_correction_compacts_unbounded_review_history(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.specification.update(
        allowed_instruments=["BTCUSDT"],
        execution_window_start="2025-05-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
        authority_boundary={
            "capital": False,
            "orders": False,
            "production_promotion": False,
            "self_approval": False,
        },
    )
    source = record.specification["research_queue"][0]
    source["instrument"] = "BTCUSDT"
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_research_context", lambda *_: {})
    monkeypatch.setattr(service, "persist_new_task", lambda *_: None)
    latest = [{"severity": "high", "message": "latest unresolved finding"}]
    cumulative = [
        {"severity": "high", "message": f"historical finding {index} " + "x" * 900}
        for index in range(60)
    ]
    correction = {
        "review_summary": "bounded correction",
        "latest_findings": latest,
        "cumulative_findings": cumulative,
    }

    task = service._create_strategy_engineering_task(
        db,
        record,
        source,
        {"category": "exact_strategy_unavailable"},
        stage="G9",
        correction_feedback=correction,
        parent_task_id=uuid4(),
    )

    evidence = json.loads(task.input_contract["evidence_context"])
    retained = evidence["independent_review_correction"]
    assert retained["cumulative_findings"] == latest
    assert retained["retained_history_count"] == 60
    assert retained["retained_history_digest"] == service.digest_document(cumulative)
    assert len(task.input_contract["evidence_context"]) <= 48_000
    ProposalEngineeringMissionContract.model_validate(task.input_contract)


def test_selected_panel_admission_is_bound_into_engineering_evidence(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.specification.update(
        allowed_instruments=["BTCUSDT", "ETHUSDT"],
        execution_window_start="2025-05-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
        authority_boundary={
            "capital": False,
            "orders": False,
            "production_promotion": False,
            "self_approval": False,
        },
    )
    binding = record.specification["dataset_bindings"][0]
    binding.update(
        catalog_id=str(uuid4()),
        lake_governance_snapshot_id=str(uuid4()),
        producer_receipt_id=str(uuid4()),
        producer_receipt_digest="4" * 64,
        partition_digests=["5" * 64],
        evidence_class="live_exchange_history",
        research_principal="alpha-research-runner",
    )
    source = record.specification["research_queue"][0]
    candidate_id = uuid4()
    source.update(
        discovery_candidate_id=str(candidate_id),
        discovery_candidate_digest="7" * 64,
        instruments=["BTCUSDT", "ETHUSDT"],
    )
    candidate = SimpleNamespace(
        candidate_digest="7" * 64,
        question=source["question"],
        document={"data": {"status": "requires_admission"}},
    )
    admission = SimpleNamespace(
        id=uuid4(),
        task_id=uuid4(),
        record_digest="8" * 64,
        assets=[{"venue": "bybit", "instrument": "BTCUSDT", "timeframe": "1m"}],
        dataset_bindings=[
            {
                key: value
                for key, value in binding.items()
                if key not in {"dataset_digest", "producer_receipt_digest"}
            }
        ],
    )
    db = MagicMock()
    db.get.return_value = candidate
    db.scalar.return_value = admission
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "citations": []},
    )
    monkeypatch.setattr(service, "persist_new_task", lambda *_: None)

    task = service._create_strategy_engineering_task(
        db, record, source, {"category": "exact_strategy_unavailable"}
    )

    evidence = json.loads(task.input_contract["evidence_context"])
    handoff = evidence["selected_panel_admission"]
    assert "dataset_binding" not in evidence
    assert handoff["candidate_id"] == str(candidate_id)
    assert handoff["status"] == "admitted"
    assert handoff["capital_or_order_authority"] is False
    assert handoff["bindings"][0]["dataset_build_id"] == binding["dataset_build_id"]
    assert len(handoff["handoff_digest"]) == 64
    assert len(evidence) <= 20
    ProposalEngineeringMissionContract.model_validate(task.input_contract)


def test_selected_panel_correction_removes_legacy_binding_idempotently(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.specification.update(
        allowed_instruments=["BTCUSDT", "ETHUSDT"],
        execution_window_start="2025-05-01T00:00:00Z",
        execution_window_end="2026-05-01T00:00:00Z",
        authority_boundary={
            "capital": False,
            "orders": False,
            "production_promotion": False,
            "self_approval": False,
        },
    )
    source = record.specification["research_queue"][0]
    source.update(
        discovery_candidate_id=str(uuid4()),
        discovery_candidate_digest="7" * 64,
        instruments=["BTCUSDT", "ETHUSDT"],
    )
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        candidate_digest="7" * 64,
        question=source["question"],
        document={"data": {"status": "requires_admission"}},
    )
    monkeypatch.setattr(
        service,
        "_selected_panel_admission_evidence",
        lambda *_: {
            "schema_version": "alpha-selected-panel-engineering-handoff-v1.0.0",
            "status": "admitted",
            "handoff_digest": "8" * 64,
        },
    )
    monkeypatch.setattr(
        service,
        "_research_context",
        lambda *_: {"corpus_digest": "9" * 64, "citations": []},
    )
    output_columns = [f"feature_{index}" for index in range(250)]
    monkeypatch.setattr(
        service,
        "_source_bindings",
        lambda *_: [
            {
                "dataset_build_id": str(uuid4()),
                "dataset_digest": "a" * 64,
                "instruments": ["BTCUSDT", "ETHUSDT"],
                "output_columns": output_columns,
                "producer_receipt_digest": "b" * 64,
            }
        ],
    )
    monkeypatch.setattr(service, "persist_new_task", lambda *_: None)
    correction = {
        "latest_findings": [
            {"severity": "medium", "message": "consolidate within 12 files"}
        ],
        "cumulative_findings": [
            {"severity": "medium", "message": "consolidate within 12 files"}
        ],
    }

    task = service._create_strategy_engineering_task(
        db,
        record,
        source,
        {"category": "exact_strategy_unavailable"},
        stage="G6",
        correction_feedback=correction,
        parent_task_id=uuid4(),
    )

    evidence = json.loads(task.input_contract["evidence_context"])
    assert "dataset_binding" not in evidence
    assert "instrument" not in evidence
    assert evidence["instruments"] == ["BTCUSDT", "ETHUSDT"]
    assert evidence["selected_panel_admission"]["status"] == "admitted"
    assert evidence["independent_review_correction"] == correction
    compact_binding = evidence["dataset_bindings"][0]
    assert "output_columns" not in compact_binding
    assert compact_binding["output_columns_count"] == len(output_columns)
    assert compact_binding["output_columns_digest"] == service.digest_document(
        output_columns
    )
    assert len(evidence) <= 20
    ProposalEngineeringMissionContract.model_validate(task.input_contract)


def test_no_change_failure_without_admission_handoff_creates_successor(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G3",
        status="failed",
        plan_digest="a" * 64,
        input_contract={
            "evidence_context": json.dumps(
                {"discovery_candidate": {"data": {"status": "requires_admission"}}}
            )
        },
        failure={
            "error_category": "executor_ExecutionPolicyError",
            "detail": "Coding agent produced no changes.",
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    successor = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=successor)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is successor
    kwargs = create.call_args.kwargs
    assert kwargs["stage"] == "G4"
    assert kwargs["parent_task_id"] == rejected.id
    assert "correction_feedback" not in kwargs


def test_correction_review_failure_carries_findings_into_next_stage(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    prior = {
        "cumulative_findings": [
            {"severity": "high", "message": "missing-bar handling is unsafe"}
        ]
    }
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G4",
        status="failed",
        plan_digest="a" * 64,
        input_contract={
            "evidence_context": json.dumps({"independent_review_correction": prior})
        },
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "cost stress is directionally incorrect",
                        "findings": [
                            {
                                "severity": "high",
                                "message": "doubled costs improve the short-side result",
                            }
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    corrected = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=corrected)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is corrected

    kwargs = create.call_args.kwargs
    assert kwargs["stage"] == "G5"
    assert kwargs["parent_task_id"] == rejected.id
    feedback = kwargs["correction_feedback"]
    assert feedback["latest_findings"] == [
        {
            "severity": "high",
            "message": "doubled costs improve the short-side result",
        }
    ]
    assert feedback["cumulative_findings"] == [
        {"severity": "high", "message": "missing-bar handling is unsafe"},
        {
            "severity": "high",
            "message": "doubled costs improve the short-side result",
        },
    ]


def test_scope_budget_failure_creates_bounded_successor(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    prior = {
        "cumulative_findings": [
            {"severity": "high", "message": "held-out evaluation is absent"}
        ]
    }
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G5",
        status="failed",
        plan_digest="a" * 64,
        input_contract={
            "evidence_context": json.dumps({"independent_review_correction": prior})
        },
        failure={
            "error_category": "executor_ExecutionPolicyError",
            "detail": "Changed-file budget exceeded.",
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    successor = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=successor)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is successor

    kwargs = create.call_args.kwargs
    assert kwargs["stage"] == "G6"
    assert kwargs["parent_task_id"] == rejected.id
    feedback = kwargs["correction_feedback"]
    assert feedback["disposition"] == (
        "consolidate_without_expanding_scope_or_weakening_gates"
    )
    assert feedback["cumulative_findings"][0] == prior["cumulative_findings"][0]
    assert "12-file" in feedback["latest_findings"][0]["message"]
    assert create.call_args.args[3] == {"category": "exact_strategy_unavailable"}


def test_reconcile_recovers_scope_budget_failure_to_g6(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.status = "needs_attention"
    failed_id = uuid4()
    record.terminal_reason = {
        "category": "governed_pipeline_task_failed",
        "task_id": str(failed_id),
    }
    failed = SimpleNamespace(
        id=failed_id,
        status="failed",
        task_number=f"A3-{record.id.hex[:8]}-001-G5",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        failure={
            "error_category": "executor_ExecutionPolicyError",
            "detail": "Changed-file budget exceeded.",
        },
    )
    db = MagicMock()
    db.get.return_value = failed
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: None)
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    advance = MagicMock(return_value=None)
    monkeypatch.setattr(service, "_advance_governed_pipeline", advance)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.phase == "strategy_engineering"
    assert record.next_action == "create_review_bound_strategy_correction"
    assert record.terminal_reason == {}
    advance.assert_called_once_with(db, record)


def test_reconcile_recovers_completed_suite_worker_timeout(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    record.status = "needs_attention"
    failed_id = uuid4()
    record.terminal_reason = {
        "category": "governed_pipeline_task_failed",
        "task_id": str(failed_id),
    }
    failed = SimpleNamespace(
        id=failed_id,
        status="failed",
        task_number=f"A3-{record.id.hex[:8]}-001-G3",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        failure={
            "error_category": "step_failed",
            "failed_step": "run-tests",
            "retryable": True,
            "execution_evidence": {
                "summary": {
                    "failure_diagnostic": {
                        "stdout_tail": (
                            "tests reached [100%]\n"
                            "scripts/queue_alpha_capacity_assignment.py:63: "
                            "SystemExit\nSystemExit: 143"
                        )
                    }
                }
            },
        },
    )
    db = MagicMock()
    db.get.return_value = failed
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: None)
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    advance = MagicMock(return_value=None)
    monkeypatch.setattr(service, "_advance_governed_pipeline", advance)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.phase == "strategy_engineering"
    assert record.next_action == "create_review_bound_strategy_correction"
    assert record.terminal_reason == {}
    advance.assert_called_once_with(db, record)


def test_validation_runtime_correction_rejects_real_test_failure():
    task = SimpleNamespace(
        id=uuid4(),
        status="failed",
        plan_digest="a" * 64,
        failure={
            "error_category": "step_failed",
            "failed_step": "run-tests",
            "retryable": True,
            "execution_evidence": {
                "summary": {
                    "failure_diagnostic": {
                        "stdout_tail": "[100%]\nFAILED tests/test_strategy.py"
                    }
                }
            },
        },
    )

    assert service._validation_runtime_correction(task) is None


def test_reconcile_retains_exhausted_g9_review_and_advances(monkeypatch):
    record = campaign(
        status="needs_attention",
        phase="complete",
        next_action="operator_review",
        completed_at=datetime.now(UTC),
    )
    failed_id = uuid4()
    record.terminal_reason = {
        "category": "governed_pipeline_task_failed",
        "task_id": str(failed_id),
    }
    failed = SimpleNamespace(
        id=failed_id,
        status="failed",
        task_number=f"A3-{record.id.hex[:8]}-001-G9",
        plan_digest="7" * 64,
        input_contract={"evidence_context": "{}"},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "The bounded implementation remains invalid.",
                        "findings": [
                            {
                                "severity": "high",
                                "message": "Held-out execution remains unreachable.",
                            }
                        ],
                    }
                },
                "artifacts": ["artifacts/review.json"],
            },
        },
    )
    db = MagicMock()
    db.get.return_value = failed
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: None)
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    monkeypatch.setattr(service, "_append_event", MagicMock())
    retained = MagicMock()
    monkeypatch.setattr(service, "record_attempt", retained)

    service.reconcile_campaign(db, record)

    assert record.status == "running"
    assert record.terminal_reason == {}
    payload = retained.call_args.args[2]
    assert payload.outcome == "invalid"
    assert payload.trial_count == 0
    assert payload.gate_report.independent_review_complete is True
    assert payload.gate_report.out_of_sample_evaluated is False
    assert payload.gate_report.qualification_authority is False
    assert payload.gate_report.shadow_eligible is False
    assert payload.evidence_digests == sorted(payload.evidence_digests)


def test_g6_review_failure_creates_g7_correction(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G6",
        status="failed",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        result={},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "end-to-end evidence remains incomplete",
                        "findings": [
                            {
                                "severity": "high",
                                "message": "native runner does not invoke the evaluator",
                            }
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    successor = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=successor)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is successor
    assert create.call_args.kwargs["stage"] == "G7"
    assert create.call_args.kwargs["parent_task_id"] == rejected.id
    assert create.call_args.kwargs["correction_feedback"]["latest_findings"] == [
        {
            "severity": "high",
            "message": "native runner does not invoke the evaluator",
        }
    ]


def test_g7_review_failure_creates_final_g8_correction(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G7",
        status="failed",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        result={},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "runner integration remains incomplete",
                        "findings": [
                            {
                                "severity": "high",
                                "message": "native artifact retention still fails",
                            }
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    successor = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=successor)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is successor
    assert create.call_args.kwargs["stage"] == "G8"
    assert create.call_args.kwargs["parent_task_id"] == rejected.id
    assert create.call_args.kwargs["correction_feedback"]["latest_findings"] == [
        {
            "severity": "high",
            "message": "native artifact retention still fails",
        }
    ]


def test_g8_review_failure_creates_final_g9_correction(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G8",
        status="failed",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        result={},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "scientific contract still fails",
                        "findings": [
                            {"severity": "high", "message": "target remains invalid"}
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    successor = SimpleNamespace(
        id=uuid4(), status="pending_approval", plan_digest="b" * 64
    )
    create = MagicMock(return_value=successor)
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    assert service._advance_governed_pipeline(db, record) is successor
    assert create.call_args.kwargs["stage"] == "G9"
    assert create.call_args.kwargs["parent_task_id"] == rejected.id


def test_final_correction_review_failure_does_not_create_unbounded_retry(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha003-governed-v1"
    rejected = SimpleNamespace(
        id=uuid4(),
        task_number=f"A3-{record.id.hex[:8]}-001-G9",
        status="failed",
        plan_digest="a" * 64,
        input_contract={"evidence_context": "{}"},
        result={},
        failure={
            "error_category": "independent_review_rejected",
            "execution_evidence": {
                "artifacts": ["artifacts/review.json"],
                "summary": {
                    "independent_review": {
                        "approved": False,
                        "summary": "scientific contract still fails",
                        "findings": [
                            {"severity": "high", "message": "target remains invalid"}
                        ],
                    }
                },
            },
        },
    )
    draft = SimpleNamespace(
        status="succeeded",
        result={
            "summary": {
                "engineering_requirement": {"category": "exact_strategy_unavailable"}
            }
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [draft, rejected]
    create = MagicMock()
    monkeypatch.setattr(service, "_create_strategy_engineering_task", create)

    assert service._advance_governed_pipeline(db, record) is rejected
    create.assert_not_called()
    assert record.status == "needs_attention"
    assert record.next_action == "strategy_engineering_failed"
    assert record.terminal_reason["task_id"] == str(rejected.id)


def test_obsolete_pending_engineering_contract_is_immutably_superseded(monkeypatch):
    record = campaign()
    source = record.specification["research_queue"][0]
    legacy = SimpleNamespace(id=uuid4(), status="pending_approval")
    approval = SimpleNamespace(status="pending")
    db = MagicMock()
    db.scalar.side_effect = [legacy, approval, None]
    decided = MagicMock()
    event = MagicMock()
    monkeypatch.setattr(service, "decide_task", decided)
    monkeypatch.setattr(service, "append_task_event", event)

    assert service._legacy_strategy_engineering_task(db, record, source) is None
    decided.assert_called_once_with(
        db,
        approval,
        actor="alpha-campaign-director",
        reason=(
            "Superseded by the production-rehearsed strategy-engineering contract "
            "with exclusive worker routing."
        ),
        action="reject",
    )
    assert legacy.status == "pending_approval"
    event.assert_called_once()


def test_failed_g2_is_retained_before_creating_g3(monkeypatch):
    record = campaign()
    source = record.specification["research_queue"][0]
    failed_g2 = SimpleNamespace(id=uuid4(), status="failed")
    db = MagicMock()
    db.scalar.side_effect = [failed_g2, None]

    assert service._legacy_strategy_engineering_task(db, record, source) is None
    assert db.scalar.call_count == 2


def test_registration_rejects_synthetic_label():
    payload = request()
    with pytest.raises(HTTPException, match="synthetic"):
        service.register_campaign(
            database(payload, provider_name="synthetic-fixture"), payload
        )


def test_registration_rejects_nonadmitted_bulletproof_receipt():
    payload = request()
    db = database(payload)
    original = db.get.side_effect

    def get(model, identity):
        value = original(model, identity)
        if model is QuantitativeProducerReceipt:
            value.receipt["result"]["admitted"] = False
        return value

    db.get.side_effect = get
    with pytest.raises(HTTPException, match="admission receipt"):
        service.register_campaign(db, payload)


def test_negative_attempt_is_retained_and_loop_continues(monkeypatch):
    record = campaign()
    record.terminal_reason = {"category": "prior_stage_pending"}
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_append_event", MagicMock())
    result = service.record_attempt(db, record, attempt(record))
    assert result.outcome == "negative"
    assert record.hypothesis_count == 1
    assert record.trial_count == 4
    assert record.status == "running"
    assert record.next_action == "compile_evidence_grounded_hypothesis"
    assert record.terminal_reason == {}


def test_positive_attempt_is_retained_without_shadow_admission(monkeypatch):
    record = campaign()
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "required_trade_logging_complete": True,
            "execution_class": "qualification",
            "qualification_authority": True,
            "failed_gates": [],
        }
    )
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_append_event", MagicMock())

    result = service.record_attempt(
        db,
        record,
        attempt(record, outcome="positive", gate_report=gate_report),
    )

    assert result.outcome == "positive"
    assert record.status == "running"
    assert record.candidate_attempt_id is None
    assert record.next_action == "compile_evidence_grounded_hypothesis"


def test_completed_positive_publication_remains_non_shadow(monkeypatch):
    record = campaign()
    record.specification["execution_protocol"] = "alpha004-delegated-v1"
    gate_report = attempt(record).gate_report.model_dump()
    gate_report.update(
        {
            "required_trade_logging_complete": True,
            "execution_class": "qualification",
            "qualification_authority": True,
            "failed_gates": [],
            "shadow_eligible": False,
        }
    )
    raw_attempt = attempt(
        record, outcome="positive", gate_report=gate_report
    ).model_dump(mode="json")
    task = SimpleNamespace(
        id=uuid4(),
        status="succeeded",
        result={
            "summary": {
                "alpha_campaign_attempt": raw_attempt,
                "publication_envelope": {"schema_version": "test-envelope"},
            }
        },
    )
    db = MagicMock()
    tasks = iter([task])
    db.scalar.side_effect = lambda *_: next(tasks, None)
    monkeypatch.setattr(service, "_append_event", MagicMock())
    monkeypatch.setattr(service, "reconcile_campaign", MagicMock())
    monkeypatch.setattr(
        "app.services.alpha_publication.publish_execution",
        lambda *_: {
            "bridge_id": str(uuid4()),
            "outcome": "positive",
            "gate_report": gate_report,
            "evidence_digests": ["1" * 64, "2" * 64, "3" * 64],
        },
    )

    assert service._consume_execution_task(db, record) is True
    assert record.status == "running"
    assert record.candidate_attempt_id is None
    assert record.next_action == "compile_evidence_grounded_hypothesis"


def test_attempt_retry_is_idempotent_before_budget_checks(monkeypatch):
    record = campaign(hypothesis_count=1, trial_count=4)
    payload = attempt(record)
    existing = SimpleNamespace(
        **payload.model_dump(exclude={"expected_campaign_digest"})
    )
    db = MagicMock()
    db.scalar.return_value = existing
    monkeypatch.setattr(service, "_append_event", MagicMock())
    assert service.record_attempt(db, record, payload) is existing
    assert record.hypothesis_count == 1
    assert record.trial_count == 4


def test_completed_execution_recovery_is_agent_bound_and_resumable(monkeypatch):
    record = campaign(
        status="completed_no_candidate",
        phase="complete",
        terminal_reason={"category": "duration_budget_exhausted"},
        completed_at=datetime.now(UTC),
    )
    task_id = uuid4()
    receipt_digest = "9" * 64
    raw_attempt = attempt(record).model_dump(mode="json")
    envelope = {
        "schema_version": "alpha003-publication-envelope-v1.0.0",
        "task_id": str(task_id),
        "campaign_digest": record.campaign_digest,
        "source_commit": COMMIT,
        "receipt_digest": receipt_digest,
        "producer_gate_report": {"capital_authority": False},
        "trial": {"bundle_digest": "8" * 64},
    }
    result = {
        "workflow": "alpha-research-execution",
        "repository": "bulletproof_bt",
        "base_commit": COMMIT,
        "task_attempt": 3,
        "success": True,
        "summary": {
            "receipt_digest": receipt_digest,
            "alpha_campaign_attempt": raw_attempt,
        },
        "downstream_handoff": {"publication_envelope": envelope},
    }
    task = SimpleNamespace(
        id=task_id,
        task_type="alpha_research_execution",
        status="failed",
        attempt_count=3,
        input_contract={
            "workflow": "alpha-research-execution",
            "base_ref": COMMIT,
            "campaign_id": str(record.id),
            "campaign_digest": record.campaign_digest,
        },
        failure={
            "error_category": "executor_ValidationError",
            "detail": "downstream handoff exceeds 32 KiB",
        },
        result={},
        completed_at=datetime.now(UTC),
        assigned_agent_id=None,
        leased_at=None,
        lease_expires_at=None,
        lease_token_prefix=None,
        lease_token_digest=None,
        last_execution_heartbeat_at=None,
    )
    agent = SimpleNamespace(id=uuid4())
    failure_event = SimpleNamespace(
        id=1,
        agent_id=agent.id,
        payload={
            "error_category": "executor_ValidationError",
            "detail": "downstream handoff exceeds 32 KiB",
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [record, None, failure_event]
    monkeypatch.setattr(service, "_append_event", MagicMock())
    monkeypatch.setattr(service, "append_task_event", MagicMock())
    consume = MagicMock(return_value=True)
    monkeypatch.setattr(service, "_consume_completed_execution_task", consume)

    recovered = service.recover_completed_execution(
        db,
        task,
        agent,
        AlphaCompletedExecutionRecovery(
            expected_campaign_digest=record.campaign_digest,
            expected_receipt_digest=receipt_digest,
            receipt_file_sha256="7" * 64,
            receipt_file_size=77_605_586,
            result=result,
            reason="Recover the immutable completed run after bounded handoff encoding failed.",
        ),
    )

    assert recovered is record
    assert task.status == "succeeded"
    assert task.result == result
    assert task.failure == {}
    assert record.status == "running"
    assert record.phase == "recovery"
    consume.assert_called_once_with(db, record, task)

    recovery_event = SimpleNamespace(
        id=2,
        agent_id=agent.id,
        payload={
            "receipt_digest": receipt_digest,
            "receipt_file_sha256": "7" * 64,
            "receipt_file_size": 77_605_586,
        },
    )
    db.scalar.side_effect = [record, recovery_event]
    with pytest.raises(HTTPException, match="attestation"):
        service.recover_completed_execution(
            db,
            task,
            SimpleNamespace(id=uuid4()),
            AlphaCompletedExecutionRecovery(
                expected_campaign_digest=record.campaign_digest,
                expected_receipt_digest=receipt_digest,
                receipt_file_sha256="7" * 64,
                receipt_file_size=77_605_586,
                result=result,
                reason="Reject a different agent replaying the completed execution receipt.",
            ),
        )

    db.scalar.side_effect = [record, recovery_event]
    service.recover_completed_execution(
        db,
        task,
        agent,
        AlphaCompletedExecutionRecovery(
            expected_campaign_digest=record.campaign_digest,
            expected_receipt_digest=receipt_digest,
            receipt_file_sha256="7" * 64,
            receipt_file_size=77_605_586,
            result=result,
            reason="Idempotently confirm the same immutable completed execution receipt.",
        ),
    )
    assert consume.call_count == 2


def test_completed_execution_recovery_rejects_other_failures(monkeypatch):
    task = SimpleNamespace(
        id=uuid4(),
        task_type="alpha_research_execution",
        status="failed",
        attempt_count=3,
        failure={"error_category": "native_execution_failed", "detail": "failed"},
    )
    record = campaign(
        status="needs_attention",
        terminal_reason={"category": "execution_task_failed", "task_id": str(task.id)},
    )
    task.input_contract = {
        "workflow": "alpha-research-execution",
        "base_ref": COMMIT,
        "campaign_id": str(record.id),
        "campaign_digest": record.campaign_digest,
    }
    agent = SimpleNamespace(id=uuid4())
    db = MagicMock()
    db.scalar.side_effect = [
        record,
        None,
        SimpleNamespace(
            id=1,
            agent_id=agent.id,
            payload={"error_category": "native_execution_failed", "detail": "failed"},
        ),
    ]
    with pytest.raises(HTTPException, match="original agent"):
        service.recover_completed_execution(
            db,
            task,
            agent,
            AlphaCompletedExecutionRecovery(
                expected_campaign_digest=record.campaign_digest,
                expected_receipt_digest="9" * 64,
                receipt_file_sha256="7" * 64,
                receipt_file_size=100,
                result={},
                reason="This unrelated native failure must remain terminal and retained.",
            ),
        )


def test_budget_exhaustion_closes_honestly(monkeypatch):
    record = campaign(hypothesis_count=2)
    record.specification["research_queue"].append(
        {
            "source_candidate_id": str(uuid4()),
            "source_candidate_digest": "7" * 64,
            "question": "Does liquidity fragmentation alter signal capacity?",
            "domain_key": "execution-science",
            "rank": 3,
        }
    )
    monkeypatch.setattr(service, "_append_event", MagicMock())
    service.reconcile_campaign(MagicMock(), record)
    assert record.status == "completed_no_candidate"
    assert record.terminal_reason["category"] == "hypothesis_budget_exhausted"


def test_duration_expiry_waits_for_inflight_execution(monkeypatch):
    record = campaign()
    record.activated_at = datetime.now(UTC) - timedelta(days=2)
    record.budget["max_duration_seconds"] = 1
    task = SimpleNamespace(
        id=uuid4(),
        task_number=f"A2-{str(record.id)[:8]}-001",
        status="running",
    )
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: task)
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    append = MagicMock()
    monkeypatch.setattr(service, "_append_event", append)

    service.reconcile_campaign(MagicMock(), record)

    assert record.status == "running"
    assert record.phase == "execution"
    assert record.next_action == "native_bulletproof_execution"
    assert record.terminal_reason == {}
    append.assert_not_called()


def test_duration_terminal_is_recovered_for_inflight_execution(monkeypatch):
    record = campaign(
        status="completed_no_candidate",
        phase="complete",
        next_action="founder_closeout_review",
        completed_at=datetime.now(UTC),
        terminal_reason={"category": "duration_budget_exhausted"},
    )
    task = SimpleNamespace(
        id=uuid4(),
        task_number=f"A2-{str(record.id)[:8]}-001",
        status="running",
    )
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: task)
    monkeypatch.setattr(service, "_consume_execution_task", lambda *_: False)
    append = MagicMock()
    monkeypatch.setattr(service, "_append_event", append)

    service.reconcile_campaign(MagicMock(), record)

    assert record.status == "running"
    assert record.phase == "execution"
    assert record.next_action == "native_bulletproof_execution"
    assert record.completed_at is None
    assert record.terminal_reason == {}
    append.assert_called_once()
    assert append.call_args.args[2] == "inflight_execution_recovered"


def test_duration_terminal_recovers_before_consuming_succeeded_execution(monkeypatch):
    record = campaign(
        status="completed_no_candidate",
        phase="complete",
        next_action="founder_closeout_review",
        completed_at=datetime.now(UTC),
        terminal_reason={"category": "duration_budget_exhausted"},
    )
    task = SimpleNamespace(
        id=uuid4(),
        task_number=f"A2-{str(record.id)[:8]}-001",
        status="succeeded",
    )
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: task)
    consume = MagicMock(return_value=True)
    monkeypatch.setattr(service, "_consume_execution_task", consume)
    monkeypatch.setattr(service, "_append_event", MagicMock())

    service.reconcile_campaign(MagicMock(), record)

    assert record.status == "running"
    assert record.completed_at is None
    consume.assert_called_once()


def test_duration_terminal_without_execution_remains_closed(monkeypatch):
    record = campaign(
        status="completed_no_candidate",
        phase="complete",
        next_action="founder_closeout_review",
        completed_at=datetime.now(UTC),
        terminal_reason={"category": "duration_budget_exhausted"},
    )
    monkeypatch.setattr(service, "_current_execution_task", lambda *_: None)
    consume = MagicMock(return_value=False)
    monkeypatch.setattr(service, "_consume_execution_task", consume)

    service.reconcile_campaign(MagicMock(), record)

    assert record.status == "completed_no_candidate"
    assert record.terminal_reason == {"category": "duration_budget_exhausted"}
    consume.assert_not_called()


def test_routes_expose_campaign_lifecycle():
    paths = {route.path for route in router.routes}
    assert {
        "/v1/research/alpha-campaigns",
        "/v1/research/alpha-campaigns/{campaign_id}",
        "/v1/research/alpha-campaigns/{campaign_id}/activate",
        "/v1/research/alpha-campaigns/{campaign_id}/attempts",
        "/v1/research/alpha-campaigns/{campaign_id}/reconcile",
        "/v1/research/alpha-campaigns/{campaign_id}/cancel",
    }.issubset(paths)
