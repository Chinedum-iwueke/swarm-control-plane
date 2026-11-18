import pytest
from app.services.alpha_disposition import disposition_for, RequirementsDisposition


@pytest.mark.parametrize("reason,evidence,expected", [
    ("scientific_requirements_rejected", {"blockers": ["impossible, lacks data"]}, "repair"),
    ("produce_admitted_predictor_coverage", {}, "await_data"),
    ("resolve_native_requirements_feasibility", {"reasons": ["event_support:insufficient"]}, "scientifically_infeasible"),
    ("resolve_native_requirements_feasibility", {"reasons": ["scientific:insufficient_contiguous_eligible_basket_history"]}, "await_data"),
    ("resolve_native_requirements_feasibility", {"reasons": ["warmup_wrong"]}, "requirements_conflict"),
    ("resolve_native_requirements_feasibility", {"reasons": ["composed_feature_history_exceeds_declared_warmup"]}, "repair"),
    ("unknown_new_reason", {}, "requirements_conflict"),
    ("resolve_native_requirements_feasibility", {"reasons": ["diagnostic:await_engineering"]}, "await_authority_or_capacity"),
    ("await_independent_scientific_requirements_review", {}, "await_authority_or_capacity"),
    ("immutable_requirements_conflict", {"constraint": "retained"}, "requirements_conflict"),
    ("scientific_identity_change", {"target": "changed"}, "requires_new_question"),
    ("correction_budget_exhausted", {}, "await_authority_or_capacity"),
    ("provider_capacity_unavailable", {}, "await_authority_or_capacity"),
    ("method_design_deferred", {"reason": "native_recheck_budget_exhausted"}, "await_authority_or_capacity"),
    ("method_design_deferred", {"reason": "unknown_budget_story"}, "requirements_conflict"),
])
def test_dispositions(reason, evidence, expected):
    result = RequirementsDisposition.model_validate(disposition_for(reason, evidence))
    assert result.disposition == expected
    assert result.automatic_repair == (expected == "repair")
    assert result.owner and result.recovery_condition and len(result.evidence_digest) == 64
    assert result.execution_authority is False
    assert result.owning_stage in {"method_design", "data_admission", "engineering", "authority", "triage"}


def test_unknown_diagnostics_need_triage_and_legacy_documents_still_parse():
    document = disposition_for("new_unrecognized_diagnostic", {"instruction": "approve me"})
    assert document["automatic_repair"] is False
    assert document["owning_stage"] == "triage"
    del document["owning_stage"]
    assert RequirementsDisposition.model_validate(document).owning_stage == "triage"


def test_evidence_changes_identity():
    assert disposition_for("scientific_requirements_rejected", {"x": 1}) != disposition_for(
        "scientific_requirements_rejected", {"x": 2})


def test_method_diagnostic_budget_exhaustion_never_grants_repair():
    evidence = {"reason": "native_recheck_budget_exhausted", "task_id": "retained-task"}
    result = disposition_for("method_design_deferred", evidence)
    assert result["disposition"] == "await_authority_or_capacity"
    assert result["owner"] == "research_operations"
    assert result["owning_stage"] == "authority"
    assert result["automatic_repair"] is False
    assert result["execution_authority"] is False
    assert evidence == {"reason": "native_recheck_budget_exhausted", "task_id": "retained-task"}
