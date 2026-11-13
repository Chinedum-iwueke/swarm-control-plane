from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services import alpha_requirements_feasibility as service
from app.services.graph import digest_document as digest
import json


def test_planning_is_content_addressed_bounded_and_preserves_parent(monkeypatch):
    producer = SimpleNamespace(id=uuid4(), project="bulletproof-bt", input_contract={"base_ref": "a" * 40},
        required_capabilities=["alpha-data-admission"], allowed_machines=["vm1-developer"])
    db = MagicMock()
    db.scalar.return_value = None
    persist = MagicMock()
    monkeypatch.setattr(service, "persist_new_task", persist)
    campaign = SimpleNamespace(id=uuid4())
    before = deepcopy(producer.input_contract)
    task = service.planning_task(db, campaign, producer, {"immutable": True})
    assert task.max_attempts == 1 and task.risk_level == 0
    assert producer.input_contract == before
    db.scalar.return_value = task
    assert service.planning_task(db, campaign, producer, {"immutable": True}) is task
    persist.assert_called_once()
    task.input_contract["feasibility_evidence"] = {"tampered": True}
    with pytest.raises(ValueError, match="identity conflict"):
        service.planning_task(db, campaign, producer, {"immutable": True})


def test_report_binds_inputs_source_and_both_native_plans():
    evidence = {"frozen": True, "validation_requirements": {"requirements": {"feature_warmup_bars": 12}}}
    plans = {}
    for mode in ("smoke", "scientific"):
        plan = {"mode": mode, "status": "ready", "source_commit": "a" * 40, "execution_authority": False}
        plans[mode] = plan | {"plan_digest": digest(plan)}
    report = {"schema_version": "native-requirements-feasibility-v1", "source_commit": "a" * 40,
        "input_digest": digest(evidence), "scientific_certification": False, "execution_authority": False,
        "status": "ready", "reasons": [], "validation_plans": plans,
        "feature_history": {"outputs": {"signal": 12}, "minimum_prior_bars": 12, "declared_warmup_bars": 12}}
    report["report_digest"] = digest(report)
    task = SimpleNamespace(result={"summary": {"native_requirements_feasibility": report}})
    assert service.verified_report(task, evidence, "a" * 40) == report
    with pytest.raises(ValueError, match="immutable inputs"):
        service.verified_report(task, {"changed": True}, "a" * 40)
    report["validation_plans"]["smoke"]["status"] = "deferred"
    report["report_digest"] = digest({k: v for k, v in report.items() if k != "report_digest"})
    with pytest.raises(ValueError, match="custody"):
        service.verified_report(task, evidence, "a" * 40)


def successor_fixture():
    from .test_alpha_coverage_successor import fixture
    parent, mandate, proposal = fixture()
    evidence = json.loads(parent.input_contract["evidence_context"])
    parts = {"feature_warmup": {"start": "2024-06-01T00:00:00Z"}, "target_tail": {"end": "2025-07-01T00:00:00Z"}}
    proposal["scientific_plan"]["partitions"] = parts
    proposal["scientific_plan"]["plan_digest"] = digest({k: v for k, v in proposal["scientific_plan"].items() if k != "plan_digest"})
    proposal["planning_inputs"]["coverage"] = [{"receipt": "exposure-filtered"}]
    proposal["successor_digest"] = digest({k: v for k, v in proposal.items() if k != "successor_digest"})
    plans = {}
    for mode in ("smoke", "scientific"):
        plan = {"status": "ready", "reasons": [], "source_commit": "a" * 40, "mode": mode, "execution_authority": False, "partitions": parts}
        plans[mode] = plan | {"plan_digest": digest(plan)}
    report = {"reasons": ["scientific:insufficient_contiguous_eligible_basket_history"],
              "feature_history": {"minimum_prior_bars": 12, "declared_warmup_bars": 12},
              "validation_plans": parent.result["summary"]["validation_plans"],
              "coverage_successor_proposal": proposal, "successor_validation_plans": plans}
    return report, evidence, mandate


def test_successor_is_proposed_for_review_without_mutating_original():
    report, evidence, mandate = successor_fixture()
    before = deepcopy(evidence)
    result = service.reviewed_successor_inputs(report, evidence, mandate, "a" * 40)
    assert result["window"] != evidence["window"]
    assert result["validation_requirements"]["requirements"] == evidence["validation_requirements"]["requirements"]
    assert evidence == before


@pytest.mark.parametrize("fault", ["warmup", "source", "requirements", "smoke", "partitions", "ledger", "mandate"])
def test_successor_cannot_hide_invalid_requirements_or_stale_custody(fault):
    report, evidence, mandate = successor_fixture()
    proposal = report["coverage_successor_proposal"]
    if fault == "warmup":
        report["feature_history"]["minimum_prior_bars"] = 13
    elif fault == "source":
        proposal["planning_inputs"]["source_commit"] = "b" * 40
    elif fault == "requirements":
        proposal["planning_inputs"]["requirements"] = {}
    elif fault == "smoke":
        plan = report["successor_validation_plans"]["smoke"]
        plan["status"] = "deferred"
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
    elif fault == "partitions":
        plan = report["successor_validation_plans"]["scientific"]
        plan["partitions"] = {}
        plan["plan_digest"] = digest({k: v for k, v in plan.items() if k != "plan_digest"})
    elif fault == "ledger":
        evidence["coverage_successor_context"]["exposure_ledger"]["complete"] = False
    else:
        mandate.mandate_digest = "e" * 64
    proposal["successor_digest"] = digest({k: v for k, v in proposal.items() if k != "successor_digest"})
    with pytest.raises(ValueError):
        service.reviewed_successor_inputs(report, evidence, mandate, "a" * 40)
