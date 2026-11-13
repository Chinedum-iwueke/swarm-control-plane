from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.services.alpha_requirements_handoff import (
    RequirementsPending,
    build_package,
    ensure_reviewed_requirements,
)
from app.services.graph import digest_document as digest


def inputs():
    requirements = {
        "research_bar_minutes": 20,
        "feature_warmup_bars": 144,
        "minimum_training_bars": 5000,
        "minimum_validation_bars": 1000,
        "minimum_test_bars": 1000,
        "target_horizon_bars": 4,
        "purge_bars": 4,
        "embargo_bars": 2,
        "minimum_scientific_window_days": 365,
        "smoke_bars": 288,
        "minimum_event_support": {"events": 40},
        "rationale": "Scientific support is separate from runner smoke validation.",
    }
    window = {"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"}
    receipt = {
        "source_commit": "a" * 40,
        "result": {
            "instrument": "TRBUSDT",
            "panel_sha256": "b" * 64,
            "admitted": True,
            "checks": {"quality": True},
        },
    }
    evidence = {
        "discovery_candidate": {
            "scientific_requirements": requirements,
            "data": {"research_timeframe": "20m", "instruments": ["TRBUSDT"]},
        },
        "selected_panel_admission": {
            "candidate_id": "candidate",
            "candidate_digest": "c" * 64,
        },
        "representation_plan": {"fixture": "representation"},
        "dataset_bindings": [
            {"instruments": ["TRBUSDT"], "partition_digests": ["b" * 64]}
        ],
    }
    clock = {
        "schema_version": "admitted-research-clock-v1",
        "representation_digest": digest(evidence["representation_plan"]),
        "window": window,
        "capital_or_order_authority": False,
        "research_bar_minutes": 20,
        "eligible_decisions_count": 26280,
        "intervals": [window],
        "point_in_time_membership_verified": False,
        "assets": {
            "TRBUSDT": {"panel_digest": "b" * 64, "admission_digest": digest(receipt)}
        },
    }
    clock["evidence_digest"] = digest(clock)
    batch = {
        "schema_version": "alpha007-selected-panel-admission-batch-v1.0.0",
        "candidate_id": "candidate",
        "candidate_digest": "c" * 64,
        "capital_or_order_authority": False,
        "predictor_coverage_evidence": clock,
        "receipts": [receipt],
    }
    return evidence, batch, {"source_commit": "a" * 40, "allowed_window": window}


def test_package_binds_final_data_clock_without_issuing_approval():
    evidence, batch, kwargs = inputs()
    before = deepcopy((evidence, batch))
    result = build_package(evidence, batch, **kwargs)
    assert result["coverage"][0]["binding_digest"] == digest(
        evidence["dataset_bindings"][0]
    )
    assert result["requirements"]["minimum_training_bars"] == 5000
    assert result["scientific_certification"] is False
    assert result["point_in_time_membership_verified"] is False
    assert "review_receipt" not in result
    assert (evidence, batch) == before


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "panel",
        "count",
        "duplicate",
        "clock",
        "representation",
        "authority",
        "window",
    ],
)
def test_rehashed_invalid_input_cannot_be_published(change):
    evidence, batch, kwargs = inputs()
    clock = batch["predictor_coverage_evidence"]
    if change == "source":
        kwargs["source_commit"] = "d" * 40
    elif change == "panel":
        evidence["dataset_bindings"][0]["partition_digests"] = ["d" * 64]
    elif change == "count":
        clock["eligible_decisions_count"] += 1
    elif change == "duplicate":
        clock["intervals"].append(clock["intervals"][0])
    elif change == "clock":
        clock["research_bar_minutes"] = 15
    elif change == "representation":
        evidence["representation_plan"] = {"different": True}
    elif change == "authority":
        batch["capital_or_order_authority"] = True
    elif change == "window":
        kwargs["allowed_window"] = kwargs["allowed_window"] | {
            "start": "2024-01-01T00:00:00Z"
        }
    clock["evidence_digest"] = digest(
        {k: v for k, v in clock.items() if k != "evidence_digest"}
    )
    with pytest.raises(ValueError):
        build_package(evidence, batch, **kwargs)


def test_missing_proposal_defers_without_paid_review_or_authoring():
    db, campaign = MagicMock(), SimpleNamespace()
    with pytest.raises(RequirementsPending):
        ensure_reviewed_requirements(db, campaign, {"discovery_candidate": {}})
    assert campaign.next_action == "propose_scientific_requirements"
    db.get.assert_not_called()
    db.add.assert_not_called()


def test_campaign_commits_pending_publication_without_returning_failed_task(
    monkeypatch,
):
    from app.services import alpha_campaign

    def pending(db, campaign):
        campaign.next_action = "await_independent_scientific_requirements_review"
        raise RequirementsPending()

    monkeypatch.setattr(alpha_campaign, "_advance_governed_pipeline_ready", pending)
    campaign = SimpleNamespace()
    assert alpha_campaign._advance_governed_pipeline(MagicMock(), campaign) is None
    assert campaign.next_action == "await_independent_scientific_requirements_review"


@pytest.mark.parametrize("verdict", [None, "reject", "approve"])
def test_durable_publication_is_reused_and_only_verified_approval_releases(
    monkeypatch, verdict
):
    from app.services import alpha_campaign
    from app.services import alpha_requirements_handoff as service

    evidence, batch, kwargs = inputs()
    evidence["window"] = kwargs["allowed_window"]
    evidence["selected_panel_admission"]["admission_task_id"] = "admission-task"
    producer = SimpleNamespace(
        status="succeeded", result={"summary": {"alpha_data_admission": batch}}
    )
    mandate = SimpleNamespace(
        mandate_digest="f" * 64,
        specification={
            "execution_window_start": kwargs["allowed_window"]["start"],
            "execution_window_end": kwargs["allowed_window"]["end"],
        },
    )
    campaign = SimpleNamespace(
        id=uuid4(),
        specification={
            "research_mandate_id": "mandate",
            "research_mandate_digest": mandate.mandate_digest,
            "bulletproof_source_commit": kwargs["source_commit"],
        },
    )
    route = SimpleNamespace(id=uuid4(), status="assigned")
    db = MagicMock()
    db.get.side_effect = lambda model, key: (
        producer if key == "admission-task" else mandate if key == "mandate" else route
    )
    events = []
    db.scalars.return_value.all.side_effect = lambda: list(events)
    identity = {
        "agent_id": str(uuid4()),
        "machine": "vm1",
        "provider": "native-bulletproof",
        "model_family": "deterministic",
        "runtime": "worker",
        "context_group": "producer",
        "package_digest": "e" * 64,
    }
    monkeypatch.setattr(service, "task_producer_identity", lambda *args: identity)
    create = MagicMock(return_value=route)
    monkeypatch.setattr(service, "create_route", create)
    monkeypatch.setattr(
        alpha_campaign, "_materialize_strategy_review_tasks", MagicMock()
    )

    def append(*args):
        event = SimpleNamespace(payload=args[-1], event_digest="a" * 64)
        events.append(event)
        return event

    monkeypatch.setattr(alpha_campaign, "_append_event", append)
    monkeypatch.setattr(
        service,
        "validated_alpha_strategy_reviews",
        lambda *args, **kwargs: (
            None if verdict is None else [SimpleNamespace(verdict=verdict)] * 2
        ),
    )
    for _ in range(2):
        if verdict == "approve":
            package = ensure_reviewed_requirements(db, campaign, evidence)
            assert package["review_receipt"]["route_id"] == str(route.id)
            assert package["scientific_certification"] is False
        else:
            with pytest.raises(RequirementsPending):
                ensure_reviewed_requirements(db, campaign, evidence)
            assert campaign.next_action == (
                "scientific_requirements_rejected"
                if verdict
                else "await_independent_scientific_requirements_review"
            )
    create.assert_called_once()
    assert len(events) == 1
