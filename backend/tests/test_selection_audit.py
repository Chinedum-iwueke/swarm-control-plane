from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.selection_audit import router
from app.schemas.selection_audit import (
    SearchFamilyLedger,
    SelectionBiasAuditCreate,
)
from app.services.research import record_digest
from app.services.selection_audit import (
    SelectionAuditConflict,
    register_selection_audit,
)
from pydantic import ValidationError

NOW = datetime(2026, 8, 27, 18, tzinfo=UTC)
MECHANISM_ID = uuid4()


def ledger(**updates) -> SearchFamilyLedger:
    trials = [
        {
            "trial_key": "trial-1",
            "specification_digest": "1" * 64,
            "status": "completed",
            "primary_metric": 1.2,
            "p_value": 0.001,
            "sharpe": 1.4,
            "sharpe_standard_error": 0.1,
        },
        {
            "trial_key": "trial-2",
            "specification_digest": "2" * 64,
            "status": "completed",
            "primary_metric": 0.2,
            "p_value": 0.4,
            "sharpe": 0.2,
            "sharpe_standard_error": 0.1,
        },
        {
            "trial_key": "trial-3",
            "specification_digest": "3" * 64,
            "status": "failed",
        },
        {
            "trial_key": "trial-4",
            "specification_digest": "4" * 64,
            "status": "cancelled",
        },
    ]
    value = {
        "schema_version": 1,
        "search_plan_digest": "a" * 64,
        "trial_family": "DISC007-FAMILY",
        "planned_trial_count": 4,
        "trials": trials,
        "reported_winner_trial_key": "trial-1",
        "stopping": {
            "rule_digest": "b" * 64,
            "rule_kind": "fixed_family",
            "stopped_after_trial": 4,
            "stop_reason": "family_complete",
            "outcome_access_before_stop": False,
        },
        "declared_researcher_degrees": ["parameter-grid", "seed-set"],
        "observed_research_operations": ["parameter-grid", "seed-set"],
        "validation_splits": [
            {"split_key": "split-1", "winner_rank": 1, "candidate_count": 4},
            {"split_key": "split-2", "winner_rank": 2, "candidate_count": 4},
            {"split_key": "split-3", "winner_rank": 1, "candidate_count": 4},
            {"split_key": "split-4", "winner_rank": 2, "candidate_count": 4},
        ],
        "finalized_at": NOW,
    }
    value.update(updates)
    return SearchFamilyLedger.model_validate(value)


def payload(document: SearchFamilyLedger, **updates) -> SelectionBiasAuditCreate:
    value = {
        "audit_key": "DISC007-AUDIT-R1",
        "mechanism_evaluation_id": MECHANISM_ID,
        "ledger": document,
        "ledger_digest": record_digest(document),
        "correction_policy": {
            "alpha": 0.05,
            "effective_trial_count": document.planned_trial_count,
            "maximum_pbo": 0.5,
        },
        "audited_by": "independent-statistical-reviewer",
    }
    value.update(updates)
    return SelectionBiasAuditCreate.model_validate(value)


def db(prior=None):
    value = MagicMock()
    value.get.return_value = SimpleNamespace(id=MECHANISM_ID)
    value.scalar.return_value = prior
    return value


def test_omitted_trial_is_rejected() -> None:
    with pytest.raises(ValidationError, match="every planned trial"):
        ledger(planned_trial_count=5)


def test_failed_trial_cannot_carry_selected_statistics() -> None:
    document = ledger().model_dump(mode="json")
    document["trials"][2]["p_value"] = 0.01
    with pytest.raises(ValidationError, match="cannot carry"):
        SearchFamilyLedger.model_validate(document)


def test_digest_drift_is_rejected() -> None:
    request = payload(ledger(), ledger_digest="f" * 64)
    with pytest.raises(SelectionAuditConflict, match="digest"):
        register_selection_audit(db(), request)


def test_complete_family_can_survive_selection_adjustment() -> None:
    record = register_selection_audit(db(), payload(ledger()))
    assert record.conclusion == "selection_adjusted"
    assert record.audit["family_wise_p"] == 0.004
    assert record.audit["benjamini_hochberg_discoveries"] == 1
    assert record.audit["promotion_authority"] is False


def test_family_wide_correction_detects_reported_winner_risk() -> None:
    document = ledger().model_dump(mode="json")
    document["trials"][0]["p_value"] = 0.02
    record = register_selection_audit(
        db(), payload(SearchFamilyLedger.model_validate(document))
    )
    assert record.conclusion == "selection_risk_detected"
    assert record.audit["family_wise_p"] == 0.08


@pytest.mark.parametrize(
    ("field", "value", "flag"),
    [
        ("outcome_access_before_stop", True, "optional_stopping"),
        ("stop_reason", "outcome_triggered", "optional_stopping"),
    ],
)
def test_optional_stopping_blocks_audit(field, value, flag) -> None:
    document = ledger().model_dump(mode="json")
    document["stopping"][field] = value
    record = register_selection_audit(
        db(), payload(SearchFamilyLedger.model_validate(document))
    )
    assert record.conclusion == "blocked"
    assert flag in record.audit["process_blocks"]


def test_undeclared_researcher_degree_blocks_audit() -> None:
    document = ledger(
        observed_research_operations=["parameter-grid", "metric-shopping"]
    )
    record = register_selection_audit(db(), payload(document))
    assert record.conclusion == "blocked"
    assert record.audit["undeclared_researcher_degrees"] == ["metric-shopping"]


def test_multiplicity_cannot_be_reduced_below_family() -> None:
    request = payload(
        ledger(), correction_policy={"alpha": 0.05, "effective_trial_count": 2}
    )
    with pytest.raises(SelectionAuditConflict, match="complete registered family"):
        register_selection_audit(db(), request)


def test_policy_thresholds_cannot_be_loosened() -> None:
    request = payload(
        ledger(),
        correction_policy={
            "alpha": 0.1,
            "effective_trial_count": 4,
            "maximum_pbo": 0.75,
        },
    )
    with pytest.raises(SelectionAuditConflict, match="alpha"):
        register_selection_audit(db(), request)


def test_validation_splits_cannot_hide_family_members() -> None:
    document = ledger().model_dump(mode="json")
    document["validation_splits"][0]["candidate_count"] = 3
    request = payload(SearchFamilyLedger.model_validate(document))
    with pytest.raises(SelectionAuditConflict, match="complete registered family"):
        register_selection_audit(db(), request)


def test_supersession_retains_prior_audit() -> None:
    prior = SimpleNamespace(
        id=uuid4(), status="active", mechanism_evaluation_id=MECHANISM_ID
    )
    request = payload(
        ledger(),
        audit_key="DISC007-AUDIT-R2",
        supersedes_audit_id=prior.id,
    )
    record = register_selection_audit(db(prior), request)
    assert prior.status == "superseded"
    assert record.supersedes_audit_id == prior.id


def test_routes_expose_selection_audits() -> None:
    assert "/v1/research/selection-audits" in {route.path for route in router.routes}
