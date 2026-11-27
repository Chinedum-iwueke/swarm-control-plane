"""Explicit pre-review repair authority, never a substitute for scientific review."""
from copy import deepcopy
from uuid import UUID

from app.models.task import Task
from app.models.alpha_discovery import AlphaCandidateDataAdmission
from app.services.graph import digest_document
from sqlalchemy import select


def native_failure_evidence(task):
    return {"task_id": str(task.id), "status": task.status,
            "input_contract": task.input_contract, "failure": task.failure}


def native_revision_scope(db, candidate, cycle, task_id, expected_digest, source):
    task = db.get(Task, UUID(str(task_id))) if task_id else None
    if task is None or digest_document(native_failure_evidence(task)) != expected_digest:
        raise ValueError("native correction evidence changed or is missing")
    contract = task.input_contract
    admission = db.scalar(select(AlphaCandidateDataAdmission).where(
        AlphaCandidateDataAdmission.candidate_id == candidate.id,
        AlphaCandidateDataAdmission.status == "admitted",
    ))
    if (task.status != "failed" or task.task_type != "alpha_data_admission"
            or (task.failure or {}).get("error_category") != "native_requirements_feasibility_failed"
            or contract.get("workflow") != "alpha-data-admission"
            or contract.get("base_ref") != source
            or contract.get("candidate_id") != str(candidate.id)
            or contract.get("candidate_digest") != candidate.candidate_digest
            or admission is None or task.parent_task_id != admission.task_id
            or contract.get("feasibility_evidence", {}).get("discovery_candidate") != candidate.document):
        raise ValueError("native correction must bind the exact admitted candidate and failed planning task")
    document = candidate.document
    specification = document.get("scientific_specification") or {}
    minima = (document.get("scientific_requirements") or {}).get("minimum_event_support") or {}
    missing = sorted({item["gate"] for item in specification.get("quantile_support_plan", [])
                      if item["gate"] not in minima})
    if not missing:
        raise ValueError("no supported deterministic defect was reproduced")
    return {"schema_version": 4, "recovery_kind": "native_contract_correction",
            "native_task_id": str(task.id), "native_evidence_digest": expected_digest,
            "finding": {"code": "undefined_support_gate_reference", "undefined_gates": missing,
                        "allowed_gates": sorted(minima), "independent_review": False},
            "rejected_method_identity": {key: deepcopy(document[key]) for key in
                ("representation_plan", "scientific_requirements", "scientific_specification", "parameter_budget")
                if document.get(key) is not None}}


def validate_native_revision(candidate, scope):
    from app.services.alpha_candidate_recovery import METHOD_FIELDS
    old = deepcopy(scope["rejected_method_identity"])
    proposed = {key: deepcopy(candidate.get(key)) for key in METHOD_FIELDS if candidate.get(key) is not None}
    for method in (old, proposed):
        if isinstance(method.get("representation_plan"), dict):
            method["representation_plan"].pop("candidate_key", None)
    old_entries = old["scientific_specification"].pop("quantile_support_plan", [])
    new_entries = proposed.get("scientific_specification", {}).pop("quantile_support_plan", [])
    if old != proposed or len(old_entries) != len(new_entries) or old_entries == new_entries:
        raise ValueError("native reference repair must only change dangling gate references")
    allowed = old["scientific_requirements"]["minimum_event_support"]
    for previous, current in zip(old_entries, new_entries):
        before, after = dict(previous), dict(current)
        prior_gate, gate = before.pop("gate"), after.pop("gate")
        if (before != after or gate not in allowed
                or (prior_gate in allowed and prior_gate != gate)):
            raise ValueError("native reference repair must preserve thresholds, partitions and valid references")
    return {"mode": "native_contract_correction", "parent_candidate_id": scope["candidate_id"],
            "parent_candidate_digest": scope["candidate_digest"],
            "native_evidence_digest": scope["native_evidence_digest"],
            "method_identity_digest": digest_document({key: candidate.get(key) for key in METHOD_FIELDS}),
            "requires_fresh_independent_review": True, "execution_authority": False}
