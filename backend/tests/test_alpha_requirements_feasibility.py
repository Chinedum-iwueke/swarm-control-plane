from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services import alpha_requirements_feasibility as service
from app.services.graph import digest_document as digest


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
