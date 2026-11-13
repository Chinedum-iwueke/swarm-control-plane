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
@pytest.mark.parametrize("native_state", ["ready", "deferred", "queued", "failed", "successor"])
def test_durable_publication_is_reused_and_only_verified_approval_releases(
    monkeypatch, verdict, native_state
):
    from app.services import alpha_campaign
    from app.services import alpha_requirements_handoff as service

    evidence, batch, kwargs = inputs()
    evidence["window"] = kwargs["allowed_window"]
    evidence["selected_panel_admission"]["admission_task_id"] = "admission-task"
    producer = SimpleNamespace(
        id=uuid4(), status="succeeded", result={"summary": {"alpha_data_admission": batch}}
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
    from app.services import alpha_requirements_feasibility as feasibility
    monkeypatch.setattr(feasibility, "planning_task", lambda *args: SimpleNamespace(id="native-plan", status=native_state if native_state in {"queued", "failed"} else "succeeded"))
    monkeypatch.setattr(feasibility, "verified_report", lambda *args: {
        "status": "deferred" if native_state == "successor" else native_state, "report_digest": "d" * 64, "reasons": [],
        "feature_history": {"minimum_prior_bars": 12}, "validation_plans": {},
        "coverage_successor_proposal": {"successor_digest": "c" * 64},
    })
    original_window = dict(evidence["window"])
    successor_window = {"start": "2024-01-01T00:00:00Z", "end": "2025-01-01T00:00:00Z"}
    monkeypatch.setattr(feasibility, "reviewed_successor_inputs", lambda report, inputs, *args: (
        inputs | {"window": successor_window} if native_state == "successor" else None
    ))
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
        if native_state not in {"ready", "successor"}:
            with pytest.raises(RequirementsPending):
                ensure_reviewed_requirements(db, campaign, evidence)
            assert campaign.next_action == {
                "queued": "await_native_requirements_feasibility",
                "failed": "repair_native_requirements_feasibility",
                "deferred": "resolve_native_requirements_feasibility",
            }[native_state]
            create.assert_not_called()
            assert not events
            continue
        if verdict == "approve":
            package = ensure_reviewed_requirements(db, campaign, evidence)
            assert package["review_receipt"]["route_id"] == str(route.id)
            assert package["scientific_certification"] is False
            if native_state == "successor":
                assert evidence["window"] == successor_window
                assert package["coverage_successor_receipt"]["successor_digest"] == "c" * 64
                # Each campaign reconciliation reconstructs the original evidence.
                evidence["window"] = dict(original_window)
        else:
            with pytest.raises(RequirementsPending):
                ensure_reviewed_requirements(db, campaign, evidence)
            assert campaign.next_action == (
                "scientific_requirements_rejected"
                if verdict
                else "await_independent_scientific_requirements_review"
            )
            assert evidence["window"] == original_window
    if native_state in {"ready", "successor"}:
        create.assert_called_once()
        assert len(events) == 1


def test_admission_reattestation_is_bounded_and_preserves_original(monkeypatch):
    from copy import deepcopy
    from app.services import alpha_campaign
    from app.services import alpha_requirements_handoff as service

    producer = SimpleNamespace(
        id=uuid4(), task_type="alpha_data_admission", risk_level=0, project="bulletproof-bt",
        input_contract={"candidate_id": str(uuid4()), "source_commit": "a" * 40},
        required_capabilities=["alpha-data-admission"], allowed_machines=["vm1-developer"],
        plan_digest="b" * 64, result={"retained": True}, status="succeeded",
    )
    before = deepcopy(vars(producer))
    db = MagicMock()
    db.scalar.return_value = None
    persist = MagicMock()
    monkeypatch.setattr(service, "persist_new_task", persist)
    monkeypatch.setattr(alpha_campaign, "_append_event", MagicMock())
    replay = service._admission_reattestation(db, SimpleNamespace(id=uuid4()), producer)
    assert replay.max_attempts == 1 and replay.risk_level == 0
    assert replay.input_contract == producer.input_contract
    assert replay.input_contract is not producer.input_contract
    assert replay.parent_task_id == producer.id
    assert vars(producer) == before
    db.scalar.return_value = replay
    assert service._admission_reattestation(db, SimpleNamespace(), producer) is replay
    persist.assert_called_once()
    replay.input_contract = {"changed": True}
    with pytest.raises(ValueError, match="scope changed"):
        service._admission_reattestation(db, SimpleNamespace(), producer)
