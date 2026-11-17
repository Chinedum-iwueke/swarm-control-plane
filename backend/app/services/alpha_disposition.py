"""Deterministic recovery routing. Reviewer prose never establishes infeasibility."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.services.graph import digest_document


class RequirementsDisposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["requirements-disposition-v1"] = "requirements-disposition-v1"
    disposition: Literal["repair", "await_data", "scientifically_infeasible",
                         "requirements_conflict", "requires_new_question",
                         "await_authority_or_capacity"]
    reason_code: str
    evidence_digest: str
    owner: str
    owning_stage: Literal["method_design", "data_admission", "engineering", "authority", "triage"] = "triage"
    recovery_condition: str
    automatic_repair: bool
    execution_authority: Literal[False] = False


ROUTES = {
    "repair": ("scientific_requirements_producer", "Publish a changed method successor; pass deterministic checks and fresh independent review."),
    "await_data": ("data_admission", "Obtain verified candidate-specific coverage or an authorized coverage successor."),
    "scientifically_infeasible": ("senior_researcher", "Revise the design under independent review or propose a new question; do not weaken support to fit history."),
    "requirements_conflict": ("research_intelligence_director", "Resolve conflicting immutable constraints through a reviewed successor; do not override them."),
    "requires_new_question": ("senior_researcher", "Submit a separately admitted question; retain the original scientific identity."),
    "await_authority_or_capacity": ("research_operations", "Restore the named authority or capacity, then recheck the unchanged evidence before scheduling."),
}


class RequirementsConstraintError(ValueError):
    def __init__(self, reason_code, message):
        super().__init__(message)
        self.reason_code = reason_code


def disposition_for(reason_code, evidence):
    # Unknown machine codes require triage, never implicit paid repair.
    repair_codes = {"scientific_requirements_rejected", "propose_scientific_specification",
                    "propose_scientific_requirements", "repair_scientific_requirements_evidence",
                    "repair_requirements_review_routing", "requirements_review_context_exceeds_bound",
                    "requirements_engineering_context_exceeds_bound", "repair_native_requirements_feasibility",
                    "repair_coverage_exposure_history", "admission_provenance_reattestation_failed"}
    kind = "repair" if reason_code in repair_codes else "requirements_conflict"
    if reason_code == "produce_admitted_predictor_coverage":
        kind = "await_data"
    elif reason_code in {"mandate_inactive", "mandate_expired", "mandate_budget_exhausted",
                         "autonomy_paused", "provider_capacity_unavailable", "correction_budget_exhausted",
                         "renew_weekly_research_mandate", "restore_requirements_mandate_binding",
                         "restore_requirements_producer_identity"}:
        kind = "await_authority_or_capacity"
    elif reason_code in {"await_native_requirements_feasibility", "await_admission_provenance_reattestation",
                         "await_independent_scientific_requirements_review"}:
        kind = "await_authority_or_capacity"
    elif reason_code == "scientific_identity_change":
        kind = "requires_new_question"
    elif reason_code == "immutable_requirements_conflict":
        kind = "requirements_conflict"
    elif reason_code == "resolve_native_requirements_feasibility":
        # These are native machine codes, not natural-language reviewer guesses.
        reasons = evidence.get("reasons", []) if isinstance(evidence, dict) else []
        if any(isinstance(r, str) and r.startswith("event_support:") for r in reasons):
            kind = "scientifically_infeasible"
        elif reasons and all(r in {"smoke:insufficient_contiguous_eligible_basket_history",
                "scientific:insufficient_contiguous_eligible_basket_history"} for r in reasons):
            kind = "await_data"
        elif reasons and all(r == "composed_feature_history_exceeds_declared_warmup" for r in reasons):
            kind = "repair"
    owner, condition = ROUTES[kind]
    stage = {"repair": "method_design", "await_data": "data_admission",
             "scientifically_infeasible": "method_design", "requires_new_question": "method_design",
             "requirements_conflict": "triage", "await_authority_or_capacity": "authority"}[kind]
    if reason_code in {"requirements_review_context_exceeds_bound", "requirements_engineering_context_exceeds_bound",
                       "repair_requirements_review_routing", "repair_native_requirements_feasibility"}:
        stage = "engineering"
    if kind == "requirements_conflict" and reason_code != "immutable_requirements_conflict":
        condition = "Classify the unrecognized or mixed diagnostic against bound evidence before any automatic repair."
    return RequirementsDisposition(disposition=kind, reason_code=reason_code,
        evidence_digest=digest_document(evidence), owner=owner, owning_stage=stage, recovery_condition=condition,
        automatic_repair=kind == "repair").model_dump(mode="json")


def retain_disposition(db, mandate, reason, evidence):
    from sqlalchemy import select
    from app.models.alpha_discovery import AlphaDiscoveryEvent
    from app.services.alpha_discovery import _event
    document = disposition_for(reason, evidence)
    key = digest_document(document)
    # The event is the durable ledger; the parent row lock serializes competing
    # check-and-insert operations without rewriting old event payloads.
    from app.models.alpha_discovery import AlphaResearchMandate
    db.execute(select(AlphaResearchMandate.id).where(
        AlphaResearchMandate.id == mandate.id).with_for_update())
    db.flush()
    if db.scalar(select(AlphaDiscoveryEvent.id).where(
            AlphaDiscoveryEvent.mandate_id == mandate.id,
            AlphaDiscoveryEvent.event_type == "requirements_disposition_recorded",
            AlphaDiscoveryEvent.payload["disposition_key"].astext == key)) is None:
        _event(db, mandate, "requirements_disposition_recorded",
               {"disposition_key": key, **document, "evidence": evidence})
    return document
