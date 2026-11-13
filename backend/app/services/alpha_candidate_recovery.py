"""Explicit source recovery is not novelty or permission to repeat observed trials."""
from uuid import UUID

from sqlalchemy import or_, select

from app.models.alpha_campaign import AlphaCampaignAttempt
from app.models.alpha_discovery import AlphaDiscoveryCandidate, AlphaDiscoveryCycle, AlphaResearchMandate
from app.models.task import Task
from app.services.graph import digest_document

SCIENTIFIC_FIELDS = ("question", "predictor", "target", "horizon", "null_hypothesis", "predicted_direction", "falsification_criteria", "features")


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


def recovery_scope(db, mandate, candidate_id, expected_digest):
    candidate = db.get(AlphaDiscoveryCandidate, UUID(str(candidate_id)))
    if candidate is None or candidate.candidate_digest != expected_digest:
        raise ValueError("retained recovery candidate changed or is missing")
    cycle = db.get(AlphaDiscoveryCycle, candidate.cycle_id)
    original = db.get(AlphaResearchMandate, cycle.mandate_id) if cycle else None
    source = mandate.specification["bulletproof_source_commit"]
    if original is None or original.specification["bulletproof_source_commit"] == source:
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
    return {
        "candidate_id": str(candidate.id), "candidate_digest": candidate.candidate_digest,
        "parent_source_commit": original.specification["bulletproof_source_commit"],
        "source_commit": source, "scientific_identity": scientific_identity,
        "novel_discovery": False, "execution_authority": False,
        "requires_fresh_admission_and_independent_review": True,
    }


def matching_recovery(db, mandate, cycle, candidate):
    context = cycle.context.get("founder_research_idea", {})
    scope = context.get("constraints", {}).get("retained_candidate_recovery")
    if not scope:
        return None
    current = recovery_scope(db, mandate, scope["candidate_id"], scope["candidate_digest"])
    if current != scope:
        raise ValueError("retained recovery scope changed")
    identity = scope["scientific_identity"]
    if any(normalized(getattr(candidate, key)) != normalized(identity[key]) for key in SCIENTIFIC_FIELDS):
        raise ValueError("retained recovery changed the scientific question")
    data = identity["data"]
    if any(getattr(candidate.data, key) != value for key, value in data.items() if key != "required_fields"):
        raise ValueError("retained recovery changed the research basket or clock")
    if panel_fields(candidate.data.required_fields, data["instruments"]) != panel_fields(data["required_fields"], data["instruments"]):
        raise ValueError("retained recovery changed the required panel inputs")
    return scope
