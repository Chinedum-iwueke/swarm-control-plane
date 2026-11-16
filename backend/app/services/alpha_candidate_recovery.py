"""Explicit source recovery is not novelty or permission to repeat observed trials."""
from uuid import UUID
from copy import deepcopy
import json

from sqlalchemy import or_, select

from app.models.alpha_campaign import AlphaCampaignAttempt
from app.models.alpha_discovery import AlphaDiscoveryCandidate, AlphaDiscoveryCycle, AlphaResearchMandate
from app.models.task import Task
from app.services.graph import digest_document
from app.services.alpha_disposition import RequirementsConstraintError

SCIENTIFIC_FIELDS = ("question", "predictor", "target", "horizon", "null_hypothesis", "predicted_direction", "falsification_criteria", "features")
METHOD_FIELDS = ("representation_plan", "scientific_requirements", "scientific_specification", "parameter_budget")


def normalized(value):
    return " ".join(str(value).lower().split())


def panel_fields(fields, instruments):
    """Compare raw requirements with their native per-panel qualified form."""
    result = set()
    for field in fields:
        if "__" in field:
            instrument, name = field.split("__", 1)
            if instrument not in instruments:
                raise ValueError("retained recovery introduced a foreign panel")
            selected = [instrument]
        else:
            selected, name = instruments, field
        # The native panel clock is an index, not a model feature column.
        if name in {"ts", "timestamp"}:
            continue
        result.update((instrument, name) for instrument in selected)
    return result


def recovery_scope(db, mandate, candidate_id, expected_digest, *, schema_version=2,
                   rejection_event_id=None, expected_rejection_digest=None):
    if schema_version not in {1, 2, 3}:
        raise ValueError("unsupported retained recovery scope version")
    candidate = db.get(AlphaDiscoveryCandidate, UUID(str(candidate_id)))
    if candidate is None or candidate.candidate_digest != expected_digest:
        raise ValueError("retained recovery candidate changed or is missing")
    cycle = db.get(AlphaDiscoveryCycle, candidate.cycle_id)
    original = db.get(AlphaResearchMandate, cycle.mandate_id) if cycle else None
    source = mandate.specification["bulletproof_source_commit"]
    if original is None or (schema_version != 3 and original.specification["bulletproof_source_commit"] == source):
        raise ValueError("source recovery requires a distinct approved native revision")
    if candidate.disposition not in {"accepted", "deferred"}:
        raise ValueError("source recovery requires a previously admissible candidate")
    question_digest = digest_document({"question": candidate.question})
    trial = db.scalar(select(AlphaCampaignAttempt.id).where(
        AlphaCampaignAttempt.question_digest == question_digest,
        AlphaCampaignAttempt.trial_count > 0,
    ).limit(1))
    execution = db.scalar(select(Task.id).where(
        Task.task_type == "alpha_research_execution",
        Task.input_contract["question_digest"].astext == question_digest,
        or_(Task.input_contract["stage"].astext.is_(None), Task.input_contract["stage"].astext.not_in(["draft", "qualify"])),
        (Task.attempt_count > 0) | Task.status.in_(["queued", "pending_approval", "leased", "running"]),
    ).limit(1))
    if trial is not None or execution is not None:
        raise ValueError("observed or in-flight scientific work cannot use untested source recovery")
    document = candidate.document
    scientific_identity = {key: document[key] for key in SCIENTIFIC_FIELDS}
    scientific_identity["data"] = {key: document["data"][key] for key in ("venue", "instruments", "research_timeframe", "liquidity_floor_usd", "required_fields")}
    scope = {
        "candidate_id": str(candidate.id), "candidate_digest": candidate.candidate_digest,
        "parent_source_commit": original.specification["bulletproof_source_commit"],
        "source_commit": source, "scientific_identity": scientific_identity,
        "novel_discovery": False, "execution_authority": False,
        "requires_fresh_admission_and_independent_review": True,
    }
    if schema_version == 2:
        scope["schema_version"] = 2
        scope["method_identity"] = {key: deepcopy(document[key]) for key in METHOD_FIELDS
                                    if document.get(key) is not None}
    if schema_version == 3:
        scope.update(method_revision_scope(db, candidate, cycle, rejection_event_id,
                                          expected_rejection_digest, scope["parent_source_commit"]))
    return scope


def method_revision_scope(db, candidate, cycle, event_id, expected_digest, parent_source):
    from app.models.alpha_campaign import AlphaCampaignEvent
    from app.models.evaluator_routing import EvaluationRoute
    from app.services.evaluator_routing import validated_alpha_strategy_reviews

    if not event_id or not expected_digest:
        raise ValueError("method correction requires exact rejection evidence")
    event = db.get(AlphaCampaignEvent, int(event_id))
    if (event is None or event.campaign_id != cycle.campaign_id
            or event.event_type != "scientific_requirements_published"):
        raise ValueError("method correction publication does not belong to this candidate's campaign")
    subject = event.payload["subject"]
    qualification = event.payload.get("qualification", {})
    card = qualification.get("card", {})
    if (subject.get("candidate_id") != str(candidate.id)
            or subject.get("review_scope") != "scientific_requirements"
            or subject.get("source_commit") != parent_source
            or card.get("source_candidate_document_digest") != digest_document(candidate.document)
            or subject.get("card_digest") != digest_document(card)
            or subject.get("artifact_bundle_digest") != digest_document(qualification.get("artifact_bundle", {}))
            or digest_document(subject) != expected_digest):
        raise ValueError("method correction rejected subject changed")
    route = db.get(EvaluationRoute, UUID(str(event.payload["route_id"])))
    if (route is None or route.subject_digest != expected_digest
            or route.subject_id != f"requirements:{candidate.id}"):
        raise ValueError("method correction review route differs from publication")
    reviews = validated_alpha_strategy_reviews(
        db, route, subject_digest=expected_digest,
        producer_agent_id=route.producer.get("agent_id"),
    )
    if not reviews or not any(review.verdict == "reject" for review in reviews):
        raise ValueError("method correction requires a validated independent rejection")
    return {
        "schema_version": 3, "recovery_kind": "scientific_method_correction",
        "rejection_event_id": event.id, "rejection_subject_digest": expected_digest,
        "rejection_route_id": str(route.id),
        "review_digest": digest_document([review.model_dump(mode="json") for review in reviews]),
        "review_blockers": sorted({item for review in reviews for item in review.blockers}),
        "rejected_method_identity": {key: deepcopy(candidate.document[key]) for key in METHOD_FIELDS
                                     if candidate.document.get(key) is not None},
    }


def validate_method_revision(candidate, scope):
    from app.schemas.alpha_discovery import AlphaScientificRequirements, AlphaScientificSpecification

    old = scope["rejected_method_identity"]
    requirements = AlphaScientificRequirements.model_validate(candidate.get("scientific_requirements"))
    previous = AlphaScientificRequirements.model_validate(old.get("scientific_requirements"))
    AlphaScientificSpecification.model_validate(candidate.get("scientific_specification"))
    for key in ("research_bar_minutes", "target_horizon_bars"):
        if getattr(requirements, key) != getattr(previous, key):
            raise RequirementsConstraintError("scientific_identity_change", "method correction cannot change the research clock or target horizon")
    for key in ("feature_warmup_bars", "minimum_training_bars", "minimum_validation_bars",
                "minimum_test_bars", "purge_bars", "embargo_bars", "minimum_scientific_window_days"):
        if getattr(requirements, key) < getattr(previous, key):
            raise RequirementsConstraintError("immutable_requirements_conflict", "method correction cannot reduce scientific support: " + key)
    unsupported = {
        key: {"required_minimum": count, "proposed_minimum": requirements.minimum_event_support.get(key)}
        for key, count in previous.minimum_event_support.items()
        if requirements.minimum_event_support.get(key, 0) < count
    }
    if unsupported:
        raise RequirementsConstraintError("immutable_requirements_conflict", "method correction cannot remove or reduce event support; preserve the exact "
                         "registered names and minima: " + json.dumps(unsupported, sort_keys=True))
    if candidate["parameter_budget"]["maximum_variants"] > old["parameter_budget"]["maximum_variants"]:
        raise ValueError("method correction cannot expand the variant budget")
    methods = {key: deepcopy(candidate.get(key)) for key in METHOD_FIELDS}
    prior = deepcopy(old)
    for value in (methods, prior):
        if isinstance(value.get("representation_plan"), dict):
            value["representation_plan"].pop("candidate_key", None)
        specification = value.get("scientific_specification", {})
        if specification.get("quantile_support_plan") == []:
            specification.pop("quantile_support_plan")
    if methods == prior:
        raise ValueError("method correction must change rejected methods, not merely retry them")
    return {"mode": "scientific_method_correction", "parent_candidate_id": scope["candidate_id"],
            "parent_candidate_digest": scope["candidate_digest"],
            "rejection_subject_digest": scope["rejection_subject_digest"],
            "method_identity_digest": digest_document(methods),
            "requires_fresh_independent_review": True, "execution_authority": False}


def apply_recovered_methods(candidate, scope):
    """A source migration reuses methods; it is not a scientific redesign."""
    if not scope or scope.get("schema_version", 1) == 1:
        return {}
    if normalized(candidate.get("question")) != normalized(scope["scientific_identity"]["question"]):
        raise ValueError("retained methods cannot be applied to another question")
    if scope.get("schema_version") == 3:
        return validate_method_revision(candidate, scope)
    if scope.get("schema_version") != 2:
        raise ValueError("unsupported retained recovery scope version")
    methods = scope.get("method_identity", {})
    if not isinstance(methods, dict) or set(methods) - set(METHOD_FIELDS):
        raise ValueError("invalid retained method identity")
    if normalized(candidate.get("question")) != normalized(scope["scientific_identity"]["question"]):
        raise ValueError("retained methods cannot be applied to another question")
    for key, value in methods.items():
        candidate[key] = deepcopy(value)
        if key == "representation_plan":
            candidate[key]["candidate_key"] = candidate["candidate_key"]
    return {"mode": "source_recovery_method_reuse", "fields": sorted(methods),
            "parent_candidate_id": scope["candidate_id"],
            "parent_candidate_digest": scope["candidate_digest"],
            "method_identity_digest": digest_document(methods),
            "requires_fresh_independent_review": True, "execution_authority": False}


def matching_recovery(db, mandate, cycle, candidate):
    context = cycle.context.get("founder_research_idea", {})
    scope = context.get("constraints", {}).get("retained_candidate_recovery")
    if not scope:
        return None
    current = recovery_scope(db, mandate, scope["candidate_id"], scope["candidate_digest"],
                             schema_version=scope.get("schema_version", 1),
                             rejection_event_id=scope.get("rejection_event_id"),
                             expected_rejection_digest=scope.get("rejection_subject_digest"))
    if current != scope:
        raise ValueError("retained recovery scope changed")
    identity = scope["scientific_identity"]
    if any(normalized(getattr(candidate, key)) != normalized(identity[key]) for key in SCIENTIFIC_FIELDS):
        raise RequirementsConstraintError("scientific_identity_change", "retained recovery changed the scientific question")
    data = identity["data"]
    if any(getattr(candidate.data, key) != value for key, value in data.items() if key != "required_fields"):
        raise ValueError("retained recovery changed the research basket or clock")
    if panel_fields(candidate.data.required_fields, data["instruments"]) != panel_fields(data["required_fields"], data["instruments"]):
        raise ValueError("retained recovery changed the required panel inputs")
    return scope
