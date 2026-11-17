"""Bounded correction seeds; never approval, scientific execution, or new authority."""
from uuid import UUID

from sqlalchemy import select

from app.models.alpha_campaign import AlphaCampaignEvent
from app.models.alpha_discovery import (
    AlphaDiscoveryCandidate, AlphaDiscoveryCycle, AlphaFounderResearchIdea, AlphaResearchMandate,
)
from app.services.alpha_candidate_recovery import recovery_scope
from app.services.graph import digest_document
from app.services.alpha_disposition import retain_disposition

MAX_CORRECTIONS = 2


def correction_worklist(scope):
    """Bind every obligation to the rejection; never infer that a fix passed."""
    items = [{"blocker_digest": digest_document(blocker), "reviewer_blocker": blocker,
              "status": "requires_proposed_correction_and_fresh_review"}
             for blocker in sorted(set(scope["review_blockers"]))]
    plan = {"schema_version": "requirements-correction-worklist-v1",
            "rejection_subject_digest": scope["rejection_subject_digest"],
            "items": items, "maximum_corrections": MAX_CORRECTIONS,
            "verification_order": ["deterministic_contract_checks", "native_feasibility",
                                   "independent_scientific_review"],
            "execution_authority": False, "scientific_approval": False}
    return {**plan, "plan_digest": digest_document(plan)}


def correction_depth(db, candidate):
    """Follow persisted parents rather than trusting an LLM-provided retry count."""
    seen = {str(candidate.id)}
    depth = 0
    while True:
        cycle = db.get(AlphaDiscoveryCycle, candidate.cycle_id)
        if cycle is None:
            raise ValueError("correction lineage cycle is missing")
        scope = (cycle.context or {}).get("founder_research_idea", {}).get(
            "constraints", {}).get("retained_candidate_recovery")
        if not scope:
            return depth
        parent_id = str(scope["candidate_id"])
        if parent_id in seen or len(seen) >= 16:
            raise ValueError("cyclic or excessive correction lineage")
        seen.add(parent_id)
        if scope.get("schema_version") == 3:
            depth += 1
        candidate = db.get(AlphaDiscoveryCandidate, UUID(parent_id))
        if candidate is None or candidate.candidate_digest != scope["candidate_digest"]:
            raise ValueError("correction parent is missing or changed")


def queue_requirements_correction(db, mandate):
    # Called by the locked mandate reconciler, only when creating a new cycle.
    from app.services.alpha_discovery import (
        _discovery_creation_paused, _event, _mandate_budget_exhausted, now,
    )
    blocked = ("mandate_inactive" if mandate.status != "active" else
        "mandate_expired" if not mandate.valid_from <= now() < mandate.valid_until else
        "mandate_budget_exhausted" if _mandate_budget_exhausted(mandate) else
        "autonomy_paused" if _discovery_creation_paused(db) else None)
    if blocked:
        retain_disposition(db, mandate, blocked, {"mandate_id": str(mandate.id)})
        return None
    # Also serialize direct reconciliation callers, not only the director tick.
    db.execute(select(AlphaResearchMandate.id).where(
        AlphaResearchMandate.id == mandate.id).with_for_update())
    publications = db.scalars(select(AlphaCampaignEvent).join(
        AlphaDiscoveryCycle, AlphaDiscoveryCycle.campaign_id == AlphaCampaignEvent.campaign_id
    ).where(
        AlphaDiscoveryCycle.mandate_id == mandate.id,
        AlphaCampaignEvent.event_type == "scientific_requirements_published",
    ).order_by(AlphaCampaignEvent.id.desc()).limit(32)).all()
    for publication in publications:
        subject = publication.payload.get("subject", {})
        try:
            candidate = db.get(AlphaDiscoveryCandidate, UUID(subject["candidate_id"]))
            if candidate is None:
                continue
            # Validates custody, actual independent rejection, and absence of trials.
            scope = recovery_scope(db, mandate, candidate.id, candidate.candidate_digest,
                schema_version=3, rejection_event_id=publication.id,
                expected_rejection_digest=digest_document(subject))
            if correction_depth(db, candidate) >= MAX_CORRECTIONS:
                retain_disposition(db, mandate, "correction_budget_exhausted", scope)
                continue
        except (ValueError, KeyError, TypeError):
            continue  # No authority can be inferred from an incomplete review.
        key = digest_document({"controller": "requirements-correction-v1",
            "mandate": mandate.mandate_digest, "candidate": candidate.candidate_digest,
            "rejection": scope["rejection_subject_digest"]})
        # Includes completed/failed seeds: unchanged evidence never receives a retry.
        if db.scalar(select(AlphaFounderResearchIdea.id).where(
                AlphaFounderResearchIdea.idea_digest == key)) is not None:
            continue
        instruments = scope["scientific_identity"]["data"]["instruments"]
        disposition = retain_disposition(db, mandate, "scientific_requirements_rejected", scope)
        worklist = correction_worklist(scope)
        idea = AlphaFounderResearchIdea(
            mandate_id=mandate.id, submitted_by="requirements-correction-controller",
            idea=("Correct the independently rejected methods for the unchanged question: "
                  + candidate.question + ". Address every retained review blocker. Preserve "
                  "scientific identity and support minima; do not claim approval or observed "
                  "power. Abstain explicitly if the corrections are infeasible."),
            constraints={"retained_candidate_recovery": scope, "requirements_disposition": disposition,
                "requirements_correction_worklist": worklist,
                "minimum_history_days": 365, "maximum_variants": min(8,
                    candidate.document["parameter_budget"]["maximum_variants"]),
                "minimum_instruments": len(instruments), "maximum_instruments": len(instruments),
                "universe_selection_policy": "preregistered_point_in_time",
                "universe_slices": ["all_eligible"],
                "selection_timing": "frozen_before_outcome_evaluation"},
            idea_digest=key, status="queued",
        )
        db.add(idea)
        db.flush()
        _event(db, mandate, "requirements_correction_queued", {
            "idea_id": str(idea.id), "parent_candidate_id": str(candidate.id),
            "rejection_subject_digest": scope["rejection_subject_digest"],
            "correction_worklist_digest": worklist["plan_digest"],
            "maximum_corrections": MAX_CORRECTIONS, "execution_authority": False,
        })
        return idea
    return None
