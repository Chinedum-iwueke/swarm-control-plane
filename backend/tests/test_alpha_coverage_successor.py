from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import json

import pytest

from app.services.alpha_coverage_successor import (
    validate_proposal,
    reconcile_coverage_successor,
)
from app.services.graph import digest_document as digest


def fixture():
    policy = {
        "envelope_start": "2023-01-02T00:00:00Z",
        "envelope_end": "2026-01-01T00:00:00Z",
        "maximum_successors": 2,
    }
    immutable = {
        "requirements": {"research_bar_minutes": 20},
        "dataset_bindings": [{"instrument": "TRB"}],
        "instruments": ["TRB"],
        "source_commit": "a" * 40,
        "variants": 8,
        "maximum_history_days": 400,
        "maximum_bar_variant_work": 1000000,
    }
    window = {"start": "2025-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"}
    lineage = digest(immutable | {"approved_window": window})
    ledger = {"lineage_digest": lineage, "complete": True, "intervals": []}
    ledger["ledger_digest"] = digest(ledger)
    evidence = {
        "window": window,
        "validation_requirements": {
            key: immutable[key]
            for key in (
                "requirements",
                "maximum_history_days",
                "maximum_bar_variant_work",
            )
        },
        "dataset_bindings": immutable["dataset_bindings"],
        "discovery_candidate": {
            "data": {"instruments": ["TRB"]},
            "parameter_budget": {"maximum_variants": 8},
        },
        "coverage_successor_context": {
            "mandate_digest": "d" * 64,
            "policy": policy,
            "prior_successors": [],
            "exposure_ledger": ledger,
        },
    }
    evidence["validation_requirements"]["coverage"] = [{"receipt": "fixture"}]
    plan = {"status": "ready", "execution_authority": False}
    plan["plan_digest"] = digest(plan)
    proposal = {
        "mandate_digest": "d" * 64,
        "policy_digest": digest(policy),
        "status": "proposed",
        "reasons": [],
        "execution_authority": False,
        "requires_independent_review": True,
        "scientific_certification": False,
        "ordinal": 1,
        "planning_inputs": immutable
        | {
            "approved_window": {
                "start": policy["envelope_start"],
                "end": policy["envelope_end"],
            }
        },
        "lineage_digest": lineage,
        "exposure_ledger_digest": ledger["ledger_digest"],
        "coverage_digest": digest(evidence["validation_requirements"]["coverage"]),
        "scientific_plan": plan,
    }
    parent_plan = {"reasons": ["insufficient_contiguous_eligible_basket_history"]}
    parent_plan["plan_digest"] = digest(parent_plan)
    proposal["parent_digest"] = parent_plan["plan_digest"]
    proposal["successor_digest"] = digest(proposal)
    parent = SimpleNamespace(
        input_contract={"evidence_context": json.dumps(evidence), "base_ref": "a" * 40},
        result={"summary": {"validation_plans": {"scientific": parent_plan}}},
    )
    mandate = SimpleNamespace(
        mandate_digest="d" * 64,
        specification={"historical_window_policy": {"coverage_replanning": policy}},
    )
    return parent, mandate, proposal


def test_proposal_binds_contract_and_mandate_without_mutation():
    parent, mandate, proposal = fixture()
    before = deepcopy(proposal)
    assert validate_proposal(parent, mandate, proposal)["window"]["start"].startswith(
        "2025"
    )
    assert proposal == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("variants", 16),
        ("source_commit", "b" * 40),
        ("requirements", {}),
        ("dataset_bindings", []),
    ],
)
def test_rehashed_proposal_cannot_change_scientific_contract(key, value):
    parent, mandate, proposal = fixture()
    proposal["planning_inputs"][key] = value
    proposal["successor_digest"] = digest(
        {k: v for k, v in proposal.items() if k != "successor_digest"}
    )
    with pytest.raises(ValueError, match="scientific contract"):
        validate_proposal(parent, mandate, proposal)


def test_legacy_failure_does_not_create_route_or_task():
    db = MagicMock()
    parent = SimpleNamespace(status="failed", result={}, failure={})
    assert reconcile_coverage_successor(db, SimpleNamespace(), parent) == (None, False)
    db.scalar.assert_not_called()


def test_repeated_reconciliation_returns_existing_child_without_new_work():
    db = MagicMock()
    child = SimpleNamespace(parent_task_id="parent")
    db.scalar.return_value = child
    parent = SimpleNamespace(
        id="parent",
        task_number="G3",
        status="failed",
        failure={},
        result={"summary": {"coverage_successor_proposal": {"status": "proposed"}}},
    )
    assert reconcile_coverage_successor(db, SimpleNamespace(), parent) == (child, True)
    db.add.assert_not_called()


@pytest.mark.parametrize("verdict", [None, "reject", "approve"])
def test_publication_review_and_materialization_are_separate_gates(
    monkeypatch, verdict
):
    import app.services.alpha_coverage_successor as service
    import app.services.alpha_campaign as campaigns

    parent, mandate, proposal = fixture()
    parent.id = uuid4()
    parent.task_number = "A3-fixture-G3"
    parent.status = "failed"
    parent.plan_digest = "f" * 64
    parent.result["summary"]["coverage_successor_proposal"] = proposal
    parent.approval_policy = {
        "kind": "bounded_hypothesis_engineering",
        "founder_approval_exempt": True,
    }
    parent.project = "bulletproof_bt"
    parent.title = parent.objective = "Fixture coverage successor authoring"
    parent.priority, parent.risk_level = 88, 1
    parent.expected_outputs = parent.acceptance_criteria = []
    parent.required_capabilities = ["alpha-strategy-engineering"]
    parent.allowed_machines = ["vm1-developer"]
    proposal["scientific_plan"]["partitions"] = {
        "feature_warmup": {"start": "2024-05-01T00:00:00Z"},
        "target_tail": {"end": "2025-05-03T00:00:00Z"},
    }
    proposal["planning_inputs"]["coverage"] = [{"fixture": "filtered"}]
    proposal["scientific_plan"]["plan_digest"] = digest(
        {k: v for k, v in proposal["scientific_plan"].items() if k != "plan_digest"}
    )
    proposal["successor_digest"] = digest(
        {k: v for k, v in proposal.items() if k != "successor_digest"}
    )
    mandate.status = "active"
    mandate.valid_from, mandate.valid_until = (
        datetime.now(UTC) - timedelta(hours=1),
        datetime.now(UTC) + timedelta(hours=1),
    )
    campaign = SimpleNamespace(
        id=uuid4(),
        specification={
            "research_mandate_id": uuid4(),
            "research_mandate_digest": mandate.mandate_digest,
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [None, mandate]
    db.scalars.return_value.all.return_value = []
    identity = {
        "agent_id": str(uuid4()),
        "machine": "vm1",
        "provider": "native-bulletproof",
        "model_family": "deterministic",
        "runtime": "worker",
        "context_group": "producer",
        "package_digest": "e" * 64,
    }
    monkeypatch.setattr(service, "task_producer_identity", lambda *a: identity)
    route = SimpleNamespace(id=uuid4(), status="assigned")
    monkeypatch.setattr(service, "create_route", lambda *a: route)
    events = []

    def append(*args):
        events.append(args[2])
        return SimpleNamespace(event_digest="p" * 64)

    monkeypatch.setattr(campaigns, "_append_event", append)
    review_tasks = MagicMock()
    monkeypatch.setattr(campaigns, "_materialize_strategy_review_tasks", review_tasks)
    monkeypatch.setattr(
        service,
        "validated_alpha_strategy_reviews",
        lambda *a, **kw: (
            None if verdict is None else [SimpleNamespace(verdict=verdict)] * 2
        ),
    )
    built = []

    def build(payload):
        built.append(payload)
        return SimpleNamespace(id=uuid4(), plan_digest="a" * 64)

    monkeypatch.setattr(service, "build_task", build)
    monkeypatch.setattr(service, "persist_new_task", lambda *a: None)
    successor, handled = reconcile_coverage_successor(db, campaign, parent)
    assert handled is True
    review_tasks.assert_called_once()
    assert events[0] == "coverage_successor_published"
    if verdict != "approve":
        assert successor is None and not built
        assert campaign.next_action == (
            "coverage_successor_rejected"
            if verdict == "reject"
            else "await_independent_coverage_successor_review"
        )
    else:
        assert events[-1] == "coverage_successor_materialized"
        assert built[0].parent_task_id == parent.id
        assert built[0].max_attempts == 1
        result = json.loads(built[0].input_contract["evidence_context"])
        assert result["window"]["start"] == "2024-05-01T00:00:00Z"
        assert "coverage_successor_context" not in result
