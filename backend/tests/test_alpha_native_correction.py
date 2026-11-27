from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.alpha_native_correction import (
    native_failure_evidence, native_revision_scope, validate_native_revision,
)
from app.services.graph import digest_document


def fixture():
    document = {"scientific_requirements": {"minimum_event_support": {"heldout": 40}},
        "scientific_specification": {"estimator": "unchanged", "quantile_support_plan": [
            {"gate": "heldout_q90", "partition": "test", "quantile": 0.9,
             "threshold_policy": "fixed_training_linear_strict_upper_tail"}]},
        "parameter_budget": {"maximum_variants": 2},
        "representation_plan": {"candidate_key": "old", "transformations": []}}
    candidate = SimpleNamespace(id=uuid4(), candidate_digest="c"*64, document=document)
    parent = uuid4()
    task = SimpleNamespace(id=uuid4(), status="failed", task_type="alpha_data_admission",
        parent_task_id=parent, failure={"error_category": "native_requirements_feasibility_failed"},
        input_contract={"workflow": "alpha-data-admission", "base_ref": "a"*40,
            "candidate_id": str(candidate.id), "candidate_digest": candidate.candidate_digest,
            "feasibility_evidence": {"discovery_candidate": deepcopy(document)}})
    db = MagicMock()
    db.get.return_value = task
    db.scalar.return_value = SimpleNamespace(task_id=parent)
    return db, task, candidate


@pytest.mark.parametrize("fault", [None, "digest", "candidate", "mixed_review"])
def test_native_correction_intake_requires_paired_distinct_evidence(fault):
    from app.schemas.alpha_discovery import AlphaFounderResearchIdeaCreate
    payload = dict(mandate_id=uuid4(), expected_mandate_digest="a"*64,
        idea="Correct native planning contract references without changing scientific requirements.",
        submitted_by="founder-operator", recovery_candidate_id=uuid4(),
        expected_recovery_candidate_digest="b"*64, native_feasibility_task_id=uuid4(),
        expected_native_feasibility_digest="c"*64)
    if fault == "digest": payload.pop("expected_native_feasibility_digest")
    elif fault == "candidate":
        payload.pop("recovery_candidate_id")
        payload.pop("expected_recovery_candidate_digest")
    elif fault == "mixed_review":
        payload.update(requirements_rejection_event_id=1, expected_requirements_rejection_digest="d"*64)
    if fault:
        with pytest.raises(ValueError): AlphaFounderResearchIdeaCreate.model_validate(payload)
    else:
        assert AlphaFounderResearchIdeaCreate.model_validate(payload).native_feasibility_task_id


@pytest.mark.parametrize("fault", [None, "digest", "source", "candidate", "parent", "document", "status", "failure", "absent_admission", "no_defect"])
def test_native_basis_requires_exact_failed_task_and_reproduced_defect(fault):
    db, task, candidate = fixture()
    if fault == "source": task.input_contract["base_ref"] = "b"*40
    elif fault == "candidate": task.input_contract["candidate_id"] = str(uuid4())
    elif fault == "parent": task.parent_task_id = uuid4()
    elif fault == "document": task.input_contract["feasibility_evidence"]["discovery_candidate"] = {}
    elif fault == "status": task.status = "running"
    elif fault == "failure": task.failure = {"error_category": "unrelated_failure"}
    elif fault == "absent_admission": db.scalar.return_value = None
    elif fault == "no_defect":
        candidate.document["scientific_specification"]["quantile_support_plan"][0]["gate"] = "heldout"
        task.input_contract["feasibility_evidence"]["discovery_candidate"] = deepcopy(candidate.document)
    digest = "f"*64 if fault == "digest" else digest_document(native_failure_evidence(task))
    if fault:
        with pytest.raises(ValueError):
            native_revision_scope(db, candidate, None, task.id, digest, "a"*40)
    else:
        scope = native_revision_scope(db, candidate, None, task.id, digest, "a"*40)
        assert scope["finding"]["independent_review"] is False
        assert scope["finding"]["undefined_gates"] == ["heldout_q90"]


@pytest.mark.parametrize("fault", [None, "unchanged", "unknown", "quantile", "partition", "minimum", "estimator", "drop"])
def test_native_repair_cannot_expand_or_weaken_scientific_contract(fault):
    db, task, candidate = fixture()
    scope = native_revision_scope(db, candidate, None, task.id,
        digest_document(native_failure_evidence(task)), "a"*40)
    scope.update(candidate_id=str(candidate.id), candidate_digest=candidate.candidate_digest)
    before = deepcopy(candidate.document)
    proposed = deepcopy(before)
    entries = proposed["scientific_specification"]["quantile_support_plan"]
    entries[0]["gate"] = "heldout"
    if fault == "unchanged": proposed = deepcopy(before)
    elif fault == "unknown": entries[0]["gate"] = "another"
    elif fault == "quantile": entries[0]["quantile"] = 0.8
    elif fault == "partition": entries[0]["partition"] = "training"
    elif fault == "minimum": proposed["scientific_requirements"]["minimum_event_support"]["heldout"] = 20
    elif fault == "estimator": proposed["scientific_specification"]["estimator"] = "different"
    elif fault == "drop": entries.clear()
    if fault:
        with pytest.raises(ValueError): validate_native_revision(proposed, scope)
    else:
        result = validate_native_revision(proposed, scope)
        assert result["execution_authority"] is False
        assert result["requires_fresh_independent_review"] is True
    assert candidate.document == before
