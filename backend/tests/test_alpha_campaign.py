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
from app.schemas.alpha_campaign import AlphaCampaignAttemptCreate, AlphaCampaignCreate
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
                {"dataset_build_id": str(uuid4()), "dataset_digest": DIGEST}
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


def test_candidate_requires_complete_no_capital_gates():
    with pytest.raises(ValidationError, match="candidate"):
        AlphaCampaignAttemptCreate.model_validate(
            attempt(campaign()).model_dump() | {"outcome": "candidate"}
        )


def test_registration_admits_real_exchange_lineage():
    payload = request()
    record = service.register_campaign(database(payload), payload)
    assert record.status == "awaiting_activation"
    assert record.specification["dataset_bindings"][0]["venue"] == "bybit"
    assert record.specification["authority_boundary"]["capital"] is False


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
    db = MagicMock()
    db.scalar.return_value = None
    monkeypatch.setattr(service, "_append_event", MagicMock())
    result = service.record_attempt(db, record, attempt(record))
    assert result.outcome == "negative"
    assert record.hypothesis_count == 1
    assert record.trial_count == 4
    assert record.status == "running"
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
