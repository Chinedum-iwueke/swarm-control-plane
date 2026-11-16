import pytest
from app.services.alpha_disposition import disposition_for, RequirementsDisposition


@pytest.mark.parametrize("reason,evidence,expected", [
    ("scientific_requirements_rejected", {"blockers": ["impossible, lacks data"]}, "repair"),
    ("produce_admitted_predictor_coverage", {}, "await_data"),
    ("resolve_native_requirements_feasibility", {"reasons": ["event_support:insufficient"]}, "scientifically_infeasible"),
    ("resolve_native_requirements_feasibility", {"reasons": ["scientific:insufficient_contiguous_eligible_basket_history"]}, "await_data"),
    ("resolve_native_requirements_feasibility", {"reasons": ["warmup_wrong"]}, "repair"),
    ("immutable_requirements_conflict", {"constraint": "retained"}, "requirements_conflict"),
    ("scientific_identity_change", {"target": "changed"}, "requires_new_question"),
    ("correction_budget_exhausted", {}, "await_authority_or_capacity"),
    ("provider_capacity_unavailable", {}, "await_authority_or_capacity"),
])
def test_dispositions(reason, evidence, expected):
    result = RequirementsDisposition.model_validate(disposition_for(reason, evidence))
    assert result.disposition == expected
    assert result.automatic_repair == (expected == "repair")
    assert result.owner and result.recovery_condition and len(result.evidence_digest) == 64
    assert result.execution_authority is False


def test_evidence_changes_identity():
    assert disposition_for("scientific_requirements_rejected", {"x": 1}) != disposition_for(
        "scientific_requirements_rejected", {"x": 2})
