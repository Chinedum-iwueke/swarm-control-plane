from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignAttempt
from app.models.alpha_discovery import (
    AlphaDiscoveryCandidate,
    AlphaDiscoveryCycle,
    AlphaDiscoveryEvent,
    AlphaFounderResearchIdea,
    AlphaResearchMandate,
)
from app.models.discovery_portfolio import DiscoveryPortfolioCandidate
from app.models.execution_telemetry import ExecutionTelemetryReplay
from app.models.task import Task
from app.schemas.alpha_campaign import (
    AlphaCampaignActivation,
    AlphaCampaignBudget,
    AlphaCampaignCreate,
)
from app.schemas.alpha_discovery import (
    AlphaFounderResearchIdeaCreate,
    AlphaPredictiveCandidate,
    AlphaResearchMandateApproval,
    AlphaResearchMandateCreate,
)
from app.schemas.discovery_portfolio import (
    DiscoveryAttentionCandidate,
    DiscoveryAttentionPolicy,
    DiscoveryPortfolioCreate,
)
from app.schemas.retrieval import HybridRetrievalRequest
from app.schemas.task import TaskCreate
from app.services.alpha_campaign import (
    activate_campaign,
    register_campaign,
    validate_real_data_bindings,
)
from app.services.discovery_portfolio import register_portfolio
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.graph import digest_document
from app.services.retrieval import hybrid_search
from app.services.tasks import build_task, persist_new_task

CLAIM_BOUNDARY = (
    "An active ALPHA-004 mandate authorizes bounded historical no-capital research only. "
    "It cannot change strategy code, enter shadow, place orders, allocate capital, approve "
    "its own evaluation or promote a candidate."
)
_TERMINAL_CYCLE = {"completed", "rejected", "needs_attention", "shadow_candidate"}
_PREDICTIVE_TERMS = {
    "predict",
    "predicts",
    "forecast",
    "forecasts",
    "lead",
    "leads",
    "subsequent",
    "next",
    "future",
}
_IMPERATIVE_PREFIXES = (
    "run ",
    "exercise ",
    "implement ",
    "build ",
    "deploy ",
    "start ",
    "finish ",
    "test ",
)
_BINDING_KEYS = {
    "dataset_build_id",
    "catalog_id",
    "lake_governance_snapshot_id",
    "producer_receipt_id",
    "dataset_key",
    "partition_digests",
    "evidence_class",
    "research_principal",
}
_LIQUIDITY_FIELDS = {
    "volume",
    "quote_volume",
    "turnover",
    "volume_usd",
    "bid_size",
    "ask_size",
}


def now() -> datetime:
    return datetime.now(UTC)


def _event(
    db: Session,
    mandate: AlphaResearchMandate,
    kind: str,
    payload: dict,
    cycle: AlphaDiscoveryCycle | None = None,
) -> None:
    prior = db.scalar(
        select(AlphaDiscoveryEvent)
        .where(AlphaDiscoveryEvent.mandate_id == mandate.id)
        .order_by(AlphaDiscoveryEvent.sequence.desc())
        .limit(1)
    )
    sequence = (prior.sequence if prior else 0) + 1
    previous = prior.event_digest if prior else None
    document = {
        "mandate_id": str(mandate.id),
        "cycle_id": str(cycle.id) if cycle else None,
        "sequence": sequence,
        "event_type": kind,
        "actor": "alpha-continuous-director",
        "payload": payload,
        "previous_digest": previous,
    }
    db.add(
        AlphaDiscoveryEvent(
            mandate_id=mandate.id,
            cycle_id=cycle.id if cycle else None,
            sequence=sequence,
            event_type=kind,
            actor="alpha-continuous-director",
            payload=payload,
            previous_digest=previous,
            event_digest=digest_document(document),
        )
    )


def _admitted_bindings(db: Session, payload: AlphaResearchMandateCreate) -> list[dict]:
    compatible = SimpleNamespace(
        allowed_venues=payload.allowed_venues,
        allowed_instruments=payload.allowed_instruments,
        dataset_bindings=payload.dataset_bindings,
        bulletproof_source_commit=payload.bulletproof_source_commit,
    )
    return validate_real_data_bindings(db, compatible)


def register_mandate(
    db: Session, payload: AlphaResearchMandateCreate
) -> AlphaResearchMandate:
    if payload.valid_until <= now():
        raise HTTPException(422, "Research mandate must end in the future.")
    admitted = _admitted_bindings(db, payload)
    specification = payload.model_dump(
        mode="json", exclude={"budget", "created_by", "dataset_bindings"}
    )
    specification["dataset_bindings"] = admitted
    specification["authority_boundary"] = {
        "capital": False,
        "orders": False,
        "shadow": False,
        "code_changes": False,
        "self_evaluation": False,
    }
    budget = payload.budget.model_dump(mode="json")
    mandate_digest = digest_document({"specification": specification, "budget": budget})
    existing = db.scalar(
        select(AlphaResearchMandate).where(
            AlphaResearchMandate.mandate_key == payload.mandate_key,
            AlphaResearchMandate.version == payload.version,
        )
    )
    if existing:
        if existing.mandate_digest != mandate_digest:
            raise HTTPException(
                409, "Mandate key and version are already bound to different content."
            )
        return existing
    mandate = AlphaResearchMandate(
        mandate_key=payload.mandate_key,
        version=payload.version,
        objective=payload.objective,
        specification=specification,
        budget=budget,
        mandate_digest=mandate_digest,
        status="awaiting_approval",
        created_by=payload.created_by,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        heartbeat_at=now(),
    )
    db.add(mandate)
    db.flush()
    _event(db, mandate, "mandate_registered", {"mandate_digest": mandate_digest})
    return mandate


def approve_mandate(
    db: Session, mandate: AlphaResearchMandate, payload: AlphaResearchMandateApproval
) -> None:
    if mandate.status != "awaiting_approval":
        raise HTTPException(409, "Only an awaiting mandate can be approved.")
    if mandate.mandate_digest != payload.expected_mandate_digest:
        raise HTTPException(409, "Mandate digest changed before approval.")
    moment = now()
    if not (mandate.valid_from <= moment < mandate.valid_until):
        raise HTTPException(409, "Mandate is outside its validity interval.")
    mandate.status = "active"
    mandate.approved_by = payload.actor
    mandate.approved_at = mandate.heartbeat_at = moment
    _event(
        db,
        mandate,
        "mandate_approved",
        {"reason": payload.reason, "expires_at": mandate.valid_until.isoformat()},
    )


def _dataset_inventory(mandate: AlphaResearchMandate) -> list[dict]:
    inventory = []
    for index, item in enumerate(mandate.specification["dataset_bindings"]):
        inventory.append(
            {
                "binding_index": index,
                "dataset_build_id": item["dataset_build_id"],
                "dataset_digest": item["dataset_digest"],
                "dataset_key": item["dataset_key"],
                "venue": item["venue"],
                "instruments": item["instruments"],
                "output_columns": item["output_columns"],
                "rows": item["rows"],
                "timeframe": "1m",
                "availability": "admitted",
            }
        )
    return inventory


def _bounded_context(db: Session, mandate: AlphaResearchMandate) -> dict:
    query = (
        mandate.objective + " predictive mechanism falsification market microstructure"
    )
    try:
        retrieval = hybrid_search(
            db, HybridRetrievalRequest(query=query, limit=12), ORCHESTRATOR_ACCESS
        )
        citations = [
            {
                "object_id": str(hit["object_id"]),
                "content_digest": hit["citation"]["content_digest"],
                "coordinates": hit["citation"]["coordinates"],
                "text": hit["text"][:1600],
                "confidence": hit["confidence"],
            }
            for hit in retrieval["hits"]
        ]
        corpus = {
            "digest": retrieval["corpus_digest"],
            "abstained": retrieval["abstained"],
            "citations": citations,
        }
    except HTTPException as exc:
        corpus = {
            "digest": None,
            "abstained": True,
            "citations": [],
            "error": str(exc.detail),
        }
    attempts = db.scalars(
        select(AlphaCampaignAttempt)
        .order_by(AlphaCampaignAttempt.created_at.desc())
        .limit(40)
    ).all()
    telemetry = db.scalars(
        select(ExecutionTelemetryReplay)
        .order_by(ExecutionTelemetryReplay.observed_at.desc())
        .limit(5)
    ).all()
    return {
        "schema_version": "alpha004-research-context-v1.0.0",
        "mandate_digest": mandate.mandate_digest,
        "objective": mandate.objective,
        "research_intelligence": corpus,
        "prior_attempts": [
            {
                "question": item.question,
                "outcome": item.outcome,
                "failed_gates": item.gate_report.get("failed_gates", []),
                "attempt_digest": item.attempt_digest,
            }
            for item in attempts
        ],
        "execution_observations": [
            {
                "venue": item.venue,
                "environment": item.environment,
                "status": item.status,
                "projection_digest": item.projection_digest,
                "summary": item.projection.get("summary", {}),
            }
            for item in telemetry
        ],
        "portfolio_gaps": ["no_current_risk004_admitted_candidate"],
        "datasets": _dataset_inventory(mandate),
        "equation_policy": {
            "llm_output_is_never_ground_truth": True,
            "allowed_statuses": [
                "source_replayed",
                "deterministically_verified",
                "pending_independent_verification",
            ],
            "campaign_use_requires": "source_replayed_or_deterministically_verified",
        },
    }


def _task(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
    stage: str,
    context: dict,
) -> Task:
    intelligence = stage == "intelligence"
    task = build_task(
        TaskCreate(
            task_number=f"A4-{str(mandate.id)[:8]}-{cycle.ordinal:03d}-{'I' if intelligence else 'H'}",
            project="systematic-research",
            task_type="alpha_discovery",
            title=(
                "Synthesize evidence for an alpha discovery cycle"
                if intelligence
                else "Propose falsifiable predictive hypotheses"
            ),
            objective=(
                "Synthesize cited mechanisms, contradictions, failures and testable gaps without proposing trades."
                if intelligence
                else "Produce typed, evidence-grounded predictive hypotheses that fit admitted point-in-time data."
            ),
            priority=80,
            risk_level=0,
            created_by="alpha-continuous-director",
            input_contract={
                "repository": "swarm-control-plane",
                "workflow": "alpha-discovery",
                "base_ref": "main",
                "stage": stage,
                "mandate_id": str(mandate.id),
                "mandate_digest": mandate.mandate_digest,
                "cycle_id": str(cycle.id),
                "maximum_candidates": mandate.budget["maximum_candidates_per_cycle"],
                "context": context,
                "authority": "no_capital_research",
            },
            expected_outputs=[
                "structured cited research brief"
                if intelligence
                else "typed falsifiable candidates"
            ],
            acceptance_criteria=[
                "all claims cite supplied immutable evidence",
                "operational instructions and vague topics are rejected",
                "no hidden holdout, capital, order, shadow or self-approval authority exists",
            ],
            approval_policy={
                "kind": "weekly_research_mandate",
                "mandate_digest": mandate.mandate_digest,
            },
            approval_required=False,
            required_capabilities=(
                ["research-intelligence", "knowledge-retrieval"]
                if intelligence
                else ["research-proposal", "prior-art"]
            ),
            allowed_machines=["vm1-developer"],
            max_attempts=3,
        )
    )
    persist_new_task(db, task)
    return task


def queue_founder_idea(
    db: Session, mandate: AlphaResearchMandate, payload: AlphaFounderResearchIdeaCreate
) -> AlphaFounderResearchIdea:
    if mandate.status != "active" or not (mandate.valid_from <= now() < mandate.valid_until):
        raise HTTPException(409, "Founder research ideas require an active weekly mandate.")
    if mandate.mandate_digest != payload.expected_mandate_digest:
        raise HTTPException(409, "Mandate digest changed before the idea was queued.")
    constraints = {
        "minimum_history_days": payload.minimum_history_days,
        "maximum_variants": payload.maximum_variants,
        "universe_selection_policy": payload.universe_selection_policy,
        "universe_slices": payload.universe_slices,
        "selection_timing": "frozen_before_outcome_evaluation",
    }
    idea_digest = digest_document(
        {
            "mandate_digest": mandate.mandate_digest,
            "idea": payload.idea,
            "constraints": constraints,
            "conversation_id": str(payload.conversation_id) if payload.conversation_id else None,
        }
    )
    existing = db.scalar(
        select(AlphaFounderResearchIdea).where(
            AlphaFounderResearchIdea.idea_digest == idea_digest
        )
    )
    if existing:
        return existing
    idea = AlphaFounderResearchIdea(
        mandate_id=mandate.id,
        conversation_id=payload.conversation_id,
        submitted_by=payload.submitted_by,
        idea=payload.idea,
        constraints=constraints,
        idea_digest=idea_digest,
        status="queued",
    )
    db.add(idea)
    db.flush()
    _event(
        db,
        mandate,
        "founder_research_idea_queued",
        {"idea_id": str(idea.id), "idea_digest": idea.idea_digest, "constraints": constraints},
    )
    return idea


def _next_founder_idea(db: Session, mandate: AlphaResearchMandate) -> AlphaFounderResearchIdea | None:
    return db.scalar(
        select(AlphaFounderResearchIdea)
        .where(
            AlphaFounderResearchIdea.mandate_id == mandate.id,
            AlphaFounderResearchIdea.status == "queued",
        )
        .order_by(AlphaFounderResearchIdea.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )


def _new_cycle(
    db: Session,
    mandate: AlphaResearchMandate,
    founder_idea: AlphaFounderResearchIdea | None = None,
) -> AlphaDiscoveryCycle:
    ordinal = mandate.cycle_count + 1
    context = _bounded_context(db, mandate)
    if founder_idea:
        context["founder_research_idea"] = {
            "id": str(founder_idea.id),
            "idea": founder_idea.idea,
            "idea_digest": founder_idea.idea_digest,
            "constraints": founder_idea.constraints,
            "instruction": (
                "Challenge this idea first. Reject it if it is not predictive, causal-timing-safe, "
                "novel, or testable with admitted data; otherwise formalize it as a candidate."
            ),
        }
    cycle_digest = digest_document(
        {
            "mandate_digest": mandate.mandate_digest,
            "ordinal": ordinal,
            "context": context,
        }
    )
    cycle = AlphaDiscoveryCycle(
        mandate_id=mandate.id,
        ordinal=ordinal,
        status="running",
        phase="intelligence_synthesis",
        next_action="await_research_intelligence_director",
        context=context,
        research_brief={},
        metrics={"generated": 0, "rejected": 0, "accepted": 0, "duplicated": 0},
        cycle_digest=cycle_digest,
        heartbeat_at=now(),
    )
    db.add(cycle)
    db.flush()
    if founder_idea:
        founder_idea.status = "processing"
        founder_idea.cycle_id = cycle.id
    task = _task(db, mandate, cycle, "intelligence", context)
    cycle.intelligence_task_id = task.id
    mandate.cycle_count = ordinal
    _event(
        db,
        mandate,
        "cycle_started",
        {
            "cycle_digest": cycle_digest,
            "task_id": str(task.id),
            "founder_idea_id": str(founder_idea.id) if founder_idea else None,
        },
        cycle,
    )
    return cycle


def _candidate_reasons(
    candidate: AlphaPredictiveCandidate,
    cycle: AlphaDiscoveryCycle,
    mandate: AlphaResearchMandate,
    prior_questions: list[str],
    db: Session | None = None,
) -> tuple[list[str], int | None]:
    reasons: list[str] = []
    founder_constraints = cycle.context.get("founder_research_idea", {}).get(
        "constraints", {}
    )
    if founder_constraints:
        maximum_variants = int(founder_constraints.get("maximum_variants", 8))
        minimum_history_days = int(
            founder_constraints.get("minimum_history_days", 365)
        )
        if candidate.parameter_budget.maximum_variants > maximum_variants:
            reasons.append("founder_variant_budget_exceeded")
        if candidate.data.minimum_history_observations < minimum_history_days * 1440:
            reasons.append("founder_minimum_history_not_requested")
        window_start = datetime.fromisoformat(
            mandate.specification["execution_window_start"]
        )
        window_end = datetime.fromisoformat(mandate.specification["execution_window_end"])
        if (window_end - window_start).total_seconds() < minimum_history_days * 86400:
            reasons.append("mandate_window_below_founder_minimum")
    question = " ".join(candidate.question.lower().split())
    words = set(question.replace("?", "").split())
    if question.startswith(_IMPERATIVE_PREFIXES):
        reasons.append("imperative_or_operational_instruction")
    if "?" not in candidate.question or not words.intersection(_PREDICTIVE_TERMS):
        reasons.append("not_explicitly_predictive")
    if len(words) < 10:
        reasons.append("vague_or_underspecified")
    evidence = cycle.context.get("research_intelligence", {}).get("citations", [])
    allowed_pairs = {(item["object_id"], item["content_digest"]) for item in evidence}
    citation_text = {
        (item["object_id"], item["content_digest"]): item.get("text", "")
        for item in evidence
    }
    supplied_pairs = {
        (str(object_id), digest)
        for object_id, digest in zip(
            candidate.evidence_object_ids, candidate.evidence_digests, strict=True
        )
    }
    if not supplied_pairs.issubset(allowed_pairs):
        reasons.append("unreplayable_evidence_citation")
    for equation in candidate.equations:
        if (
            str(equation.source_object_id),
            equation.source_content_digest,
        ) not in allowed_pairs:
            reasons.append("unreplayable_equation_source")
        if equation.verification == "pending_independent_verification":
            reasons.append("equation_verification_pending")
        if equation.verification == "source_replayed":
            compact_expression = "".join(equation.expression.split())
            compact_source = "".join(equation.source_excerpt.split())
            compact_citation = "".join(
                citation_text.get(
                    (str(equation.source_object_id), equation.source_content_digest),
                    "",
                ).split()
            )
            if (
                compact_expression not in compact_source
                or compact_source not in compact_citation
            ):
                reasons.append("equation_source_replay_mismatch")
            reasons.append("equation_verification_required_for_campaign")
        if equation.verification in {
            "deterministically_verified",
            "independently_verified",
        }:
            valid_receipt = False
            if db is not None and equation.verification_receipt_digest:
                from app.services.scientific_assurance import receipt_matches_equation

                valid_receipt = receipt_matches_equation(
                    db,
                    equation.verification_receipt_digest,
                    source_object_id=equation.source_object_id,
                    source_content_digest=equation.source_content_digest,
                    expression=equation.expression,
                    required_level=(
                        "independently_verified"
                        if equation.verification == "independently_verified"
                        else "machine_verified"
                    ),
                )
            if not valid_receipt:
                reasons.append("equation_assurance_receipt_invalid_or_unbound")
    binding_index = None
    for item in cycle.context.get("datasets", []):
        required_fields = set(candidate.data.required_fields)
        output_columns = set(item.get("output_columns", []))
        if (
            item["venue"] == candidate.data.venue
            and candidate.data.instrument in item["instruments"]
            and item["timeframe"] == candidate.data.timeframe
            and item["rows"] >= candidate.data.minimum_history_observations
            and required_fields.issubset(output_columns)
            and bool(required_fields & _LIQUIDITY_FIELDS)
        ):
            binding_index = item["binding_index"]
            break
    if binding_index is None:
        reasons.append("data002_003_availability_not_demonstrated")
    if (
        candidate.data.liquidity_floor_usd
        < mandate.specification["minimum_liquidity_usd"]
    ):
        reasons.append("liquidity_floor_below_mandate")
    normalized_prior = {" ".join(item.lower().split()) for item in prior_questions}
    if question in normalized_prior:
        reasons.append("duplicate_prior_question")
    if any(_question_similarity(question, item) >= 0.8 for item in normalized_prior):
        reasons.append("semantic_duplicate_prior_question")
    return sorted(set(reasons)), binding_index


def _question_similarity(first: str, second: str) -> float:
    left = {word for word in first.replace("?", "").split() if len(word) > 2}
    right = {word for word in second.replace("?", "").split() if len(word) > 2}
    return len(left & right) / len(left | right) if left or right else 1.0


def _materialize_candidates(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
    raw: list[dict],
) -> list[AlphaDiscoveryCandidate]:
    prior_questions = [
        item.question for item in db.scalars(select(AlphaCampaignAttempt)).all()
    ] + [item.question for item in db.scalars(select(AlphaDiscoveryCandidate)).all()]
    records = []
    for raw_candidate in raw[: mandate.budget["maximum_candidates_per_cycle"]]:
        try:
            candidate = AlphaPredictiveCandidate.model_validate(raw_candidate)
            assured_equations = []
            for equation in candidate.equations:
                if equation.verification == "source_replayed":
                    from app.services.scientific_assurance import assure_source_equation

                    receipt = assure_source_equation(
                        db,
                        source_object_id=equation.source_object_id,
                        source_content_digest=equation.source_content_digest,
                        expression=equation.expression,
                        purpose=f"ALPHA-004 candidate {candidate.candidate_key}",
                        requested_by="alpha-continuous-director",
                    )
                    if receipt:
                        equation = equation.model_copy(
                            update={
                                "verification": "deterministically_verified",
                                "verification_receipt_digest": receipt.record_digest,
                            }
                        )
                assured_equations.append(equation)
            candidate = candidate.model_copy(update={"equations": assured_equations})
            reasons, binding_index = _candidate_reasons(
                candidate, cycle, mandate, prior_questions, db
            )
            document = candidate.model_dump(mode="json") | {
                "dataset_binding_index": binding_index
            }
        except ValidationError as exc:
            candidate = None
            reasons = ["candidate_schema_invalid"]
            document = {"raw": raw_candidate, "validation_error": type(exc).__name__}
        key = (
            candidate.candidate_key if candidate else f"invalid-{len(records) + 1:03d}"
        )
        question = (
            candidate.question
            if candidate
            else str(raw_candidate.get("question", "invalid candidate"))[:2000]
        )
        disposition = "accepted" if not reasons else "rejected"
        digest = digest_document(
            {
                "cycle_digest": cycle.cycle_digest,
                "candidate_key": key,
                "document": document,
                "disposition": disposition,
                "reason_codes": reasons,
            }
        )
        record = AlphaDiscoveryCandidate(
            cycle_id=cycle.id,
            candidate_key=key,
            question=question,
            document=document,
            disposition=disposition,
            reason_codes=reasons,
            candidate_digest=digest,
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def _portfolio_and_campaign(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
    accepted: list[AlphaDiscoveryCandidate],
) -> None:
    if len(accepted) < 2:
        cycle.status = "rejected"
        cycle.phase = "complete"
        cycle.next_action = "schedule_next_discovery_cycle"
        cycle.completed_at = now()
        _event(
            db,
            mandate,
            "cycle_insufficient_candidates",
            {"accepted": len(accepted)},
            cycle,
        )
        return
    candidates = [
        DiscoveryAttentionCandidate(
            candidate_key=item.candidate_key,
            domain_key=item.document["domain_key"],
            cluster_key=item.document["cluster_key"],
            source_type="alpha_discovery_candidate",
            source_id=item.id,
            source_digest=item.candidate_digest,
            question=item.question,
            decision_relevance=item.document["expected_information_gain"],
            feasibility=item.document["feasibility"],
            attention_cost=1,
        )
        for item in accepted
    ]
    maximum = min(len(candidates), mandate.budget["maximum_candidates_per_cycle"])
    portfolio = register_portfolio(
        db,
        DiscoveryPortfolioCreate(
            portfolio_key=f"ALPHA004-{str(mandate.id)[:8]}-{cycle.ordinal:03d}",
            version="1.0.0",
            project="bulletproof-bt",
            objective=f"ALPHA-004 replenishment cycle {cycle.ordinal}: {mandate.objective}",
            source_epoch=now(),
            policy=DiscoveryAttentionPolicy(
                attention_budget=maximum,
                maximum_selected=maximum,
                minimum_distinct_domains=1,
                maximum_per_domain=maximum,
                maximum_per_cluster=maximum,
            ),
            candidates=candidates,
            created_by="alpha-continuous-director",
        ),
    )
    selected = db.scalars(
        select(DiscoveryPortfolioCandidate).where(
            DiscoveryPortfolioCandidate.portfolio_id == portfolio.id,
            DiscoveryPortfolioCandidate.selected.is_(True),
        )
    ).all()
    campaign = register_campaign(
        db,
        AlphaCampaignCreate(
            campaign_key=f"ALPHA004-{str(mandate.id)[:8]}-{cycle.ordinal:03d}",
            version="1.0.0",
            project="bulletproof-bt",
            objective=mandate.objective,
            discovery_portfolio_id=portfolio.id,
            dataset_bindings=[
                {key: value for key, value in binding.items() if key in _BINDING_KEYS}
                for binding in mandate.specification["dataset_bindings"]
            ],
            bulletproof_source_commit=mandate.specification[
                "bulletproof_source_commit"
            ],
            allowed_venues=mandate.specification["allowed_venues"],
            allowed_instruments=mandate.specification["allowed_instruments"],
            budget=AlphaCampaignBudget(
                max_hypotheses=len(selected),
                max_total_trials=min(
                    mandate.budget["maximum_total_trials"] - mandate.trial_count,
                    len(selected) * mandate.budget["maximum_variants_per_hypothesis"],
                ),
                max_variants_per_hypothesis=mandate.budget[
                    "maximum_variants_per_hypothesis"
                ],
                max_duration_seconds=min(
                    604800,
                    max(3600, int((mandate.valid_until - now()).total_seconds())),
                ),
                max_consecutive_failures=mandate.budget["maximum_consecutive_failures"],
            ),
            execution_protocol="alpha004-delegated-v1",
            execution_window_start=mandate.specification["execution_window_start"],
            execution_window_end=mandate.specification["execution_window_end"],
            research_mandate_id=mandate.id,
            research_mandate_digest=mandate.mandate_digest,
            created_by="alpha-continuous-director",
        ),
    )
    activate_campaign(
        db,
        campaign,
        AlphaCampaignActivation(
            expected_campaign_digest=campaign.campaign_digest,
            actor="alpha-continuous-director",
            reason="Activated within the exact founder-approved weekly no-capital mandate.",
        ),
    )
    cycle.discovery_portfolio_id = portfolio.id
    cycle.campaign_id = campaign.id
    cycle.phase = "campaign"
    cycle.next_action = "await_bounded_bulletproof_results"
    _event(
        db,
        mandate,
        "campaign_replenished",
        {
            "portfolio_id": str(portfolio.id),
            "campaign_id": str(campaign.id),
            "campaign_digest": campaign.campaign_digest,
        },
        cycle,
    )


def reconcile_mandate(db: Session, mandate: AlphaResearchMandate) -> None:
    moment = now()
    mandate.heartbeat_at = moment
    if mandate.status != "active":
        return
    if moment >= mandate.valid_until:
        mandate.status = "expired"
        _event(db, mandate, "mandate_expired", {"expired_at": moment.isoformat()})
        return
    cycle = db.scalar(
        select(AlphaDiscoveryCycle)
        .where(AlphaDiscoveryCycle.mandate_id == mandate.id)
        .order_by(AlphaDiscoveryCycle.ordinal.desc())
        .limit(1)
    )
    if cycle is None:
        _new_cycle(db, mandate, _next_founder_idea(db, mandate))
        return
    cycle.heartbeat_at = moment
    if cycle.campaign_id:
        campaign = db.get(AlphaCampaign, cycle.campaign_id)
        if campaign and campaign.status == "shadow_candidate":
            cycle.status = "shadow_candidate"
            cycle.phase = "complete"
            cycle.next_action = "founder_shadow_review"
            cycle.completed_at = moment
            mandate.status = "paused_for_shadow_review"
            _event(
                db,
                mandate,
                "shadow_candidate_reached",
                {"campaign_id": str(campaign.id)},
                cycle,
            )
        elif campaign and campaign.status == "completed_no_candidate":
            cycle.status = "completed"
            cycle.phase = "complete"
            cycle.next_action = "schedule_next_discovery_cycle"
            cycle.completed_at = moment
            mandate.hypothesis_count += campaign.hypothesis_count
            mandate.trial_count += campaign.trial_count
            _event(
                db,
                mandate,
                "campaign_completed_without_candidate",
                {
                    "campaign_id": str(campaign.id),
                    "hypotheses": campaign.hypothesis_count,
                    "trials": campaign.trial_count,
                },
                cycle,
            )
        elif campaign and campaign.status == "needs_attention":
            cycle.status = "needs_attention"
            cycle.next_action = campaign.next_action
        return
    if cycle.status in _TERMINAL_CYCLE:
        founder_idea = db.scalar(
            select(AlphaFounderResearchIdea).where(AlphaFounderResearchIdea.cycle_id == cycle.id)
        )
        if founder_idea and founder_idea.status == "processing":
            founder_idea.status = "completed" if cycle.status == "completed" else cycle.status
        elapsed = (moment - (cycle.completed_at or cycle.created_at)).total_seconds()
        if (
            mandate.cycle_count >= mandate.budget["maximum_cycles"]
            or mandate.hypothesis_count >= mandate.budget["maximum_hypotheses"]
            or mandate.trial_count >= mandate.budget["maximum_total_trials"]
        ):
            mandate.status = "completed"
            _event(
                db,
                mandate,
                "mandate_budget_exhausted",
                {
                    "cycles": mandate.cycle_count,
                    "hypotheses": mandate.hypothesis_count,
                    "trials": mandate.trial_count,
                },
            )
        elif (queued := _next_founder_idea(db, mandate)) is not None:
            _new_cycle(db, mandate, queued)
        elif elapsed >= mandate.budget["cadence_seconds"]:
            _new_cycle(db, mandate)
        return
    intelligence = db.get(Task, cycle.intelligence_task_id)
    if intelligence is None or intelligence.status not in {
        "succeeded",
        "failed",
        "cancelled",
    }:
        return
    if intelligence.status != "succeeded":
        cycle.status = "needs_attention"
        cycle.next_action = "repair_research_intelligence_worker"
        _event(
            db,
            mandate,
            "intelligence_stage_failed",
            {"task_id": str(intelligence.id)},
            cycle,
        )
        return
    output = intelligence.result.get("summary", {}).get("alpha_discovery_output", {})
    brief = output.get("research_brief")
    if not isinstance(brief, dict):
        cycle.status = "needs_attention"
        cycle.next_action = "review_invalid_intelligence_output"
        return
    cycle.research_brief = brief
    if cycle.hypothesis_task_id is None:
        task = _task(
            db, mandate, cycle, "hypothesis", {**cycle.context, "research_brief": brief}
        )
        cycle.hypothesis_task_id = task.id
        cycle.phase = "hypothesis_generation"
        cycle.next_action = "await_senior_researcher"
        _event(db, mandate, "hypothesis_task_created", {"task_id": str(task.id)}, cycle)
        return
    hypothesis = db.get(Task, cycle.hypothesis_task_id)
    if hypothesis is None or hypothesis.status not in {
        "succeeded",
        "failed",
        "cancelled",
    }:
        return
    if hypothesis.status != "succeeded":
        cycle.status = "needs_attention"
        cycle.next_action = "repair_senior_researcher"
        _event(
            db,
            mandate,
            "hypothesis_stage_failed",
            {"task_id": str(hypothesis.id)},
            cycle,
        )
        return
    raw = (
        hypothesis.result.get("summary", {})
        .get("alpha_discovery_output", {})
        .get("candidates", [])
    )
    records = _materialize_candidates(
        db, mandate, cycle, raw if isinstance(raw, list) else []
    )
    accepted = [item for item in records if item.disposition == "accepted"]
    cycle.metrics = {
        "generated": len(records),
        "accepted": len(accepted),
        "rejected": len(records) - len(accepted),
        "duplicated": sum(
            bool(
                {"duplicate_prior_question", "semantic_duplicate_prior_question"}
                & set(item.reason_codes)
            )
            for item in records
        ),
    }
    _portfolio_and_campaign(db, mandate, cycle, accepted)


def reconcile_all(db: Session) -> list[AlphaResearchMandate]:
    mandates = db.scalars(
        select(AlphaResearchMandate)
        .where(AlphaResearchMandate.status == "active")
        .order_by(AlphaResearchMandate.created_at)
        .with_for_update(skip_locked=True)
    ).all()
    for mandate in mandates:
        reconcile_mandate(db, mandate)
    return mandates


def serialize_mandate(mandate: AlphaResearchMandate) -> dict:
    return {
        key: getattr(mandate, key)
        for key in (
            "id",
            "mandate_key",
            "version",
            "objective",
            "specification",
            "budget",
            "mandate_digest",
            "status",
            "cycle_count",
            "hypothesis_count",
            "trial_count",
            "created_by",
            "approved_by",
            "created_at",
            "valid_from",
            "valid_until",
            "approved_at",
            "heartbeat_at",
        )
    }


def overview(db: Session) -> dict:
    mandates = db.scalars(
        select(AlphaResearchMandate)
        .order_by(AlphaResearchMandate.created_at.desc())
        .limit(30)
    ).all()
    cycles = db.scalars(
        select(AlphaDiscoveryCycle)
        .order_by(AlphaDiscoveryCycle.created_at.desc())
        .limit(100)
    ).all()
    founder_ideas = db.scalars(
        select(AlphaFounderResearchIdea)
        .order_by(AlphaFounderResearchIdea.created_at.desc())
        .limit(100)
    ).all()
    counts = dict(
        db.execute(
            select(AlphaDiscoveryCandidate.disposition, func.count()).group_by(
                AlphaDiscoveryCandidate.disposition
            )
        ).all()
    )
    attempted = dict(
        db.execute(
            select(AlphaCampaignAttempt.outcome, func.count()).group_by(
                AlphaCampaignAttempt.outcome
            )
        ).all()
    )
    compiled = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.task_number.like("A3-%-Q"), Task.status == "succeeded")
        )
        or 0
    )
    agents = db.scalars(
        select(Agent).where(
            Agent.slug.in_(
                [
                    "vm1-research-intelligence-director",
                    "vm1-m13-senior-research-specialist",
                    "vm1-alpha004-research-intelligence-director",
                    "vm1-alpha004-senior-researcher",
                    "vm1-alpha-research-executor-v2",
                ]
            )
        )
    ).all()
    stalls = [
        {
            "cycle_id": str(item.id),
            "phase": item.phase,
            "next_action": item.next_action,
            "heartbeat_at": item.heartbeat_at,
        }
        for item in cycles
        if item.status == "needs_attention"
        or (
            item.status == "running"
            and (now() - item.heartbeat_at).total_seconds() > 300
        )
    ]
    return {
        "generated_at": now(),
        "mandates": [serialize_mandate(item) for item in mandates],
        "cycles": [
            {
                "id": str(item.id),
                "mandate_id": str(item.mandate_id),
                "ordinal": item.ordinal,
                "status": item.status,
                "phase": item.phase,
                "next_action": item.next_action,
                "metrics": item.metrics,
                "campaign_id": str(item.campaign_id) if item.campaign_id else None,
                "heartbeat_at": item.heartbeat_at,
            }
            for item in cycles
        ],
        "founder_ideas": [
            {
                "id": str(item.id),
                "mandate_id": str(item.mandate_id),
                "cycle_id": str(item.cycle_id) if item.cycle_id else None,
                "idea": item.idea,
                "idea_digest": item.idea_digest,
                "constraints": item.constraints,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in founder_ideas
        ],
        "throughput": {
            "generated": sum(counts.values()),
            "rejected": counts.get("rejected", 0),
            "accepted": counts.get("accepted", 0),
            "duplicated": db.scalar(
                select(func.count())
                .select_from(AlphaDiscoveryCandidate)
                .where(
                    AlphaDiscoveryCandidate.reason_codes.contains(
                        ["semantic_duplicate_prior_question"]
                    )
                )
            )
            or 0,
            "compiled": compiled,
            "tested": sum(attempted.values()),
            "falsified": attempted.get("negative", 0),
            "invalid": attempted.get("invalid", 0),
            "failed": attempted.get("failed", 0),
            "shadow_candidates": attempted.get("candidate", 0),
            "awaiting_engineering": db.scalar(
                select(func.count())
                .select_from(AlphaCampaign)
                .where(
                    AlphaCampaign.status == "needs_attention",
                    AlphaCampaign.phase == "strategy_engineering",
                )
            )
            or 0,
        },
        "stalls": stalls,
        "agents": [
            {
                "slug": item.slug,
                "status": item.status,
                "presence": "online"
                if item.last_heartbeat_at
                and (now() - item.last_heartbeat_at).total_seconds() <= 90
                else "offline",
                "last_heartbeat_at": item.last_heartbeat_at,
            }
            for item in agents
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
