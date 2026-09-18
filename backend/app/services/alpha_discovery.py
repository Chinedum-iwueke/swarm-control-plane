from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.alpha_campaign import AlphaCampaign, AlphaCampaignAttempt
from app.models.alpha_discovery import (
    AlphaCandidateDataAdmission,
    AlphaDiscoveryCandidate,
    AlphaDiscoveryCycle,
    AlphaDiscoveryEvent,
    AlphaFounderResearchIdea,
    AlphaResearchMandate,
)
from app.models.discovery_portfolio import DiscoveryPortfolioCandidate
from app.models.execution_telemetry import ExecutionTelemetryReplay
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.schemas.alpha_campaign import (
    AlphaCampaignActivation,
    AlphaCampaignBudget,
    AlphaCampaignCreate,
)
from app.schemas.alpha_discovery import (
    AlphaFounderResearchIdeaCreate,
    AlphaPredictiveCandidate,
    AlphaRepresentationPlan,
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
from app.services.alpha_data_admission import register_selected_panel_receipt
from app.services.discovery_portfolio import register_portfolio
from app.services.evidence import ORCHESTRATOR_ACCESS
from app.services.graph import digest_document
from app.services.quantitative_receipt import lake_inventory_summary
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
    db.scalar(
        select(AlphaResearchMandate.id)
        .where(AlphaResearchMandate.id == mandate.id)
        .with_for_update()
    )
    db.flush()
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


def _discovery_catalog(db: Session, payload: AlphaResearchMandateCreate) -> dict | None:
    binding = payload.discovery_catalog
    if binding is None:
        return None
    record = db.get(QuantitativeProducerReceipt, binding.producer_receipt_id)
    if (
        record is None
        or record.milestone != "DATA-002"
        or record.producer != "bt.institutional.lake_manifest.manifest_catalog_receipt"
        or record.receipt_digest != binding.receipt_digest
        or record.source_commit != binding.source_commit
        or any(record.receipt.get("authority", {}).values())
    ):
        raise HTTPException(
            422,
            "Discovery catalog binding is not an immutable no-authority manifest receipt.",
        )
    result = record.receipt.get("result", {})
    if (
        result.get("schema_version") != "data002-manifest-catalog-v1.0.0"
        or not set(binding.allowed_venues).issubset(set(result.get("venue_scope", [])))
        or result.get("execution_eligible") is not False
    ):
        raise HTTPException(
            422, "Discovery catalog does not cover the requested venue scope."
        )
    return binding.model_dump(mode="json") | {
        "one_year_candidate_count": len(result.get("one_year_coverage_candidates", [])),
        "execution_authority": False,
    }


def register_mandate(
    db: Session, payload: AlphaResearchMandateCreate
) -> AlphaResearchMandate:
    if payload.valid_until <= now():
        raise HTTPException(422, "Research mandate must end in the future.")
    strategy_catalog = payload.strategy_catalog
    if (
        strategy_catalog.source_commit != payload.bulletproof_source_commit
        or digest_document(
            strategy_catalog.model_dump(mode="json", exclude={"catalog_digest"})
        )
        != strategy_catalog.catalog_digest
    ):
        raise HTTPException(
            422, "Strategy capability catalog is not bound to the reviewed source."
        )
    admitted = _admitted_bindings(db, payload)
    discovery_catalog = _discovery_catalog(db, payload)
    specification = payload.model_dump(
        mode="json", exclude={"budget", "created_by", "dataset_bindings"}
    )
    specification["dataset_bindings"] = admitted
    if discovery_catalog is not None:
        specification["discovery_catalog"] = discovery_catalog
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


def _discovery_queries(mandate) -> list[str]:
    columns = {
        column
        for binding in mandate.specification["dataset_bindings"]
        for column in binding["output_columns"]
    }
    facets = []
    if "close" in columns:
        facets.extend(["momentum transaction costs", "mean reversion short horizon"])
    if {"high", "low", "close"}.issubset(columns):
        facets.append("volatility return predictability")
    if "volume" in columns:
        facets.extend(["liquidity price impact", "volume return predictability"])
    if "funding_rate" in columns:
        facets.append("funding carry reversal")
    if facets:
        offset = mandate.cycle_count % len(facets)
        facets = (facets[offset:] + facets[:offset])[:3]
    return list(dict.fromkeys([mandate.objective[:1000], *facets]))


def _discovery_corpus(db, mandate) -> dict:
    queries = _discovery_queries(mandate)
    citations = {}
    receipts = []
    corpus_digest = None
    try:
        for query in queries:
            retrieval = hybrid_search(
                db, HybridRetrievalRequest(query=query, limit=6), ORCHESTRATOR_ACCESS
            )
            current_digest = retrieval["corpus_digest"]
            if corpus_digest is not None and corpus_digest != current_digest:
                raise HTTPException(409, "Corpus changed during discovery grounding.")
            corpus_digest = current_digest
            receipts.append(
                {
                    "query": query,
                    "abstained": retrieval["abstained"],
                    "confidence": retrieval["confidence"],
                    "corpus_digest": current_digest,
                }
            )
            for hit in retrieval["hits"][:3]:
                key = str(hit["object_id"])
                if key in citations:
                    citations[key]["retrieved_for"].append(query)
                    continue
                citations[key] = {
                    "object_id": key,
                    "content_digest": hit["citation"]["content_digest"],
                    "coordinates": hit["citation"]["coordinates"],
                    "text": hit["text"][:1600],
                    "confidence": hit["confidence"],
                    "retrieved_for": [query],
                }
        return {
            "digest": corpus_digest,
            "abstained": not citations,
            "citations": list(citations.values()),
            "query_receipts": receipts,
        }
    except HTTPException as exc:
        return {
            "digest": None,
            "abstained": True,
            "citations": [],
            "query_receipts": receipts,
            "error": str(exc.detail),
        }


def _bounded_context(db: Session, mandate: AlphaResearchMandate) -> dict:
    corpus = _discovery_corpus(db, mandate)
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
    catalog_binding = mandate.specification.get("discovery_catalog")
    catalog = (
        lake_inventory_summary(
            db,
            receipt_id=catalog_binding["producer_receipt_id"],
            receipt_digest=catalog_binding["receipt_digest"],
        )
        if catalog_binding
        else lake_inventory_summary(db)
    )
    catalog["discovery_authority"] = bool(catalog_binding)
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
        "lake_catalog": catalog,
        "strategy_catalog": mandate.specification["strategy_catalog"],
        "research_constraints": {
            "minimum_liquidity_usd": mandate.specification["minimum_liquidity_usd"],
            "liquidity_measurement_fields": sorted(_LIQUIDITY_FIELDS),
            "historical_group_labels_are_not_mandatory_universes": True,
            "maximum_variants_per_hypothesis": mandate.budget[
                "maximum_variants_per_hypothesis"
            ],
            "execution_window_start": mandate.specification["execution_window_start"],
            "execution_window_end": mandate.specification["execution_window_end"],
            "bulletproof_source_commit": mandate.specification[
                "bulletproof_source_commit"
            ],
            "universe_selection": (
                "preregister before outcomes; manifest-visible assets may be proposed, "
                "but only content-admitted panels may execute"
            ),
            "maximum_assets_per_hypothesis": (
                catalog_binding.get("maximum_assets_per_hypothesis", 1)
                if catalog_binding
                else 1
            ),
            "catalog_visibility_is_not_execution_admission": True,
            "new_code_requires_explicit_approval": True,
            "capital_or_order_authority": False,
        },
        "equation_policy": {
            "llm_output_is_never_ground_truth": True,
            "allowed_statuses": [
                "source_replayed",
                "deterministically_verified",
                "pending_independent_verification",
            ],
            "campaign_use_requires": "bound_deterministic_or_independent_verification_receipt",
        },
    }


def _task(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
    stage: str,
    context: dict,
) -> Task:
    stage_code = {"intelligence": "I", "hypothesis": "H", "representation": "R"}[stage]
    titles = {
        "intelligence": "Synthesize evidence for an alpha discovery cycle",
        "hypothesis": "Propose falsifiable predictive hypotheses",
        "representation": "Select causal data representations for predictive hypotheses",
    }
    objectives = {
        "intelligence": "Synthesize cited mechanisms, contradictions, failures and testable gaps without proposing trades.",
        "hypothesis": "Produce typed, evidence-grounded predictive hypotheses that fit visible point-in-time data.",
        "representation": "Select point-in-time baskets, transformations and complete-bar timeframes without inspecting outcomes.",
    }
    capabilities = {
        "intelligence": ["research-intelligence", "knowledge-retrieval"],
        "hypothesis": ["research-proposal", "prior-art"],
        "representation": ["data-representation", "market-data-read"],
    }
    task = build_task(
        TaskCreate(
            task_number=f"A4-{str(mandate.id)[:8]}-{cycle.ordinal:03d}-{stage_code}",
            project="systematic-research",
            task_type="alpha_discovery",
            title=titles[stage],
            objective=objectives[stage],
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
                {
                    "intelligence": "structured cited research brief",
                    "hypothesis": "typed falsifiable candidates",
                    "representation": "pre-outcome data representation plans",
                }[stage]
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
            required_capabilities=capabilities[stage],
            allowed_machines=["vm1-developer"],
            max_attempts=3,
        )
    )
    persist_new_task(db, task)
    return task


def queue_founder_idea(
    db: Session, mandate: AlphaResearchMandate, payload: AlphaFounderResearchIdeaCreate
) -> AlphaFounderResearchIdea:
    if mandate.status != "active" or not (
        mandate.valid_from <= now() < mandate.valid_until
    ):
        raise HTTPException(
            409, "Founder research ideas require an active weekly mandate."
        )
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
            "conversation_id": str(payload.conversation_id)
            if payload.conversation_id
            else None,
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
        {
            "idea_id": str(idea.id),
            "idea_digest": idea.idea_digest,
            "constraints": constraints,
        },
    )
    return idea


def _next_founder_idea(
    db: Session, mandate: AlphaResearchMandate
) -> AlphaFounderResearchIdea | None:
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
    *,
    prepared_context: dict | None = None,
) -> AlphaDiscoveryCycle:
    ordinal = mandate.cycle_count + 1
    context = (
        prepared_context
        if prepared_context is not None
        else _bounded_context(db, mandate)
    )
    if founder_idea:
        context = _focus_founder_context(context, founder_idea.idea)
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


def _focus_founder_context(context: dict, idea: str) -> dict:
    """Keep explicit founder challenges inside the model's useful context window."""
    focused = deepcopy(context)
    normalized_idea = idea.upper()
    idea_tokens = set(re.findall(r"[A-Z0-9]+(?:[-_][A-Z0-9]+)*", normalized_idea))

    lake_catalog = focused.get("lake_catalog", {})
    assets = lake_catalog.get("assets", [])
    named_instruments = {
        str(item[-1]).upper()
        for item in assets
        if item and str(item[-1]).upper() in idea_tokens
    }
    if named_instruments:
        lake_catalog["assets"] = [
            item
            for item in assets
            if item and str(item[-1]).upper() in named_instruments
        ]
        candidates = lake_catalog.get("one_year_coverage_candidates", [])
        lake_catalog["one_year_coverage_candidates"] = [
            item
            for item in candidates
            if str(item.get("instrument") or item.get("symbol") or "").upper()
            in named_instruments
        ]

    strategy_catalog = focused.get("strategy_catalog", {})
    capabilities = strategy_catalog.get("capabilities", [])
    selected_capabilities = [
        capability
        for capability in capabilities
        if str(capability.get("hypothesis_id", "")).upper() in idea_tokens
        or str(capability.get("contract_digest", "")).upper() in normalized_idea
        or str(capability.get("research_contract_digest", "")).upper()
        in normalized_idea
    ]
    if selected_capabilities:
        strategy_catalog["capabilities"] = selected_capabilities

    focused["founder_context_focus"] = {
        "named_instruments": sorted(named_instruments),
        "strategy_hypothesis_ids": [
            item["hypothesis_id"] for item in selected_capabilities
        ],
        "selection_basis": "explicit_founder_idea_references",
        "server_side_validation_unchanged": True,
    }
    return focused


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
        minimum_history_days = int(founder_constraints.get("minimum_history_days", 365))
        if candidate.parameter_budget.maximum_variants > maximum_variants:
            reasons.append("founder_variant_budget_exceeded")
        if candidate.data.minimum_history_observations < minimum_history_days * 1440:
            reasons.append("founder_minimum_history_not_requested")
        window_start = datetime.fromisoformat(
            mandate.specification["execution_window_start"]
        )
        window_end = datetime.fromisoformat(
            mandate.specification["execution_window_end"]
        )
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
            and set(candidate.data.instruments).issubset(set(item["instruments"]))
            and item["timeframe"] == candidate.data.timeframe
            and item["rows"] >= candidate.data.minimum_history_observations
            and required_fields.issubset(output_columns)
            and bool(required_fields & _LIQUIDITY_FIELDS)
        ):
            binding_index = item["binding_index"]
            break
    if binding_index is None:
        catalog = cycle.context.get("lake_catalog", {})
        visible = {
            (
                str(item.get("venue", "")).lower(),
                str(item.get("instrument", "")).upper(),
            )
            for item in catalog.get("one_year_coverage_candidates", [])
            if item.get("fetch_status") == "success"
            and int(item.get("missing_rows") or 0) == 0
            and item.get("timeframe") == candidate.data.timeframe
        }
        requested = {
            (candidate.data.venue, instrument)
            for instrument in candidate.data.instruments
        }
        maximum_assets = int(
            mandate.specification.get("discovery_catalog", {}).get(
                "maximum_assets_per_hypothesis", 1
            )
        )
        if (
            catalog.get("discovery_authority") is True
            and requested
            and requested.issubset(visible)
            and len(requested) <= maximum_assets
        ):
            reasons.append("data_admission_required")
        else:
            reasons.append("data002_003_availability_not_demonstrated")
    if (
        candidate.data.liquidity_floor_usd
        < mandate.specification["minimum_liquidity_usd"]
    ):
        reasons.append("liquidity_floor_below_mandate")
    if candidate.reusable_hypothesis_id is not None:
        capability = next(
            (
                item
                for item in mandate.specification["strategy_catalog"]["capabilities"]
                if item["hypothesis_id"] == candidate.reusable_hypothesis_id
            ),
            None,
        )
        if capability is None:
            reasons.append("reusable_hypothesis_not_in_frozen_catalog")
        elif not capability["bounded_weekly_reuse_eligible"]:
            reasons.append("reusable_hypothesis_exceeds_weekly_variant_budget")
        elif len(candidate.data.instruments) > capability["maximum_instruments"]:
            reasons.append("reusable_hypothesis_input_cardinality_mismatch")
        elif candidate.data.research_timeframe not in capability["signal_timeframes"]:
            reasons.append("reusable_hypothesis_timeframe_mismatch")
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


def _apply_representation_plans(
    raw_candidates: list[dict], raw_plans: list[dict]
) -> tuple[list[dict], dict]:
    """Bind one independently selected, outcome-blind representation per candidate."""
    candidates = {
        item.get("candidate_key"): dict(item)
        for item in raw_candidates
        if isinstance(item, dict) and isinstance(item.get("candidate_key"), str)
    }
    if len(candidates) != len(raw_candidates):
        raise ValueError("candidate keys must be present and unique")
    plans: dict[str, AlphaRepresentationPlan] = {}
    for document in raw_plans:
        plan = AlphaRepresentationPlan.model_validate(document)
        if plan.candidate_key in plans:
            raise ValueError("representation plans must have unique candidate keys")
        plans[plan.candidate_key] = plan
    if set(plans) != set(candidates):
        raise ValueError(
            "representation plans must cover exactly the frozen candidates"
        )
    bound = []
    audit = {}
    for key, candidate in candidates.items():
        plan = plans[key]
        candidate["data"] = {
            "venue": plan.venue,
            "instrument": plan.instrument,
            "instruments": plan.instruments,
            "timeframe": plan.source_timeframe,
            "research_timeframe": plan.research_timeframe,
            "resampling_policy": plan.resampling_policy,
            "required_fields": plan.required_fields,
            "minimum_history_observations": plan.minimum_history_observations,
            "liquidity_floor_usd": plan.liquidity_floor_usd,
        }
        bound.append(candidate)
        audit[key] = {
            "data": candidate["data"],
            "transformation_rationale": plan.transformation_rationale,
            "rejected_alternatives": plan.rejected_alternatives,
            "outcome_data_consulted": False,
        }
    return bound, audit


def _candidate_enters_novelty_memory(item: AlphaDiscoveryCandidate) -> bool:
    return not (
        item.disposition == "rejected"
        and "candidate_schema_invalid" in item.reason_codes
    )


def _materialize_candidates(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
    raw: list[dict],
) -> list[AlphaDiscoveryCandidate]:
    prior_candidates = db.scalars(select(AlphaDiscoveryCandidate)).all()
    prior_questions = [
        item.question for item in db.scalars(select(AlphaCampaignAttempt)).all()
    ] + [
        item.question
        for item in prior_candidates
        if _candidate_enters_novelty_memory(item)
    ]
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
                "dataset_binding_index": binding_index,
                "reusable_strategy_capability": next(
                    (
                        item
                        for item in mandate.specification["strategy_catalog"][
                            "capabilities"
                        ]
                        if item["hypothesis_id"] == candidate.reusable_hypothesis_id
                    ),
                    None,
                ),
            }
        except ValidationError as exc:
            candidate = None
            reasons = ["candidate_schema_invalid"]
            document = {
                "raw": raw_candidate,
                "validation_error": {
                    "type": type(exc).__name__,
                    "errors": exc.errors(include_url=False, include_input=False),
                },
            }
        key = (
            candidate.candidate_key if candidate else f"invalid-{len(records) + 1:03d}"
        )
        question = (
            candidate.question
            if candidate
            else str(raw_candidate.get("question", "invalid candidate"))[:2000]
        )
        disposition = (
            "accepted"
            if not reasons
            else "awaiting_data_admission"
            if reasons == ["data_admission_required"]
            else "rejected"
        )
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
    for record in records:
        if record.disposition == "awaiting_data_admission":
            _ensure_data_admission_task(db, mandate, record)
    return records


def _ensure_data_admission_task(
    db: Session,
    mandate: AlphaResearchMandate,
    candidate: AlphaDiscoveryCandidate,
) -> AlphaCandidateDataAdmission:
    existing = db.scalar(
        select(AlphaCandidateDataAdmission).where(
            AlphaCandidateDataAdmission.candidate_id == candidate.id
        )
    )
    if existing is not None:
        return existing
    catalog = mandate.specification.get("discovery_catalog")
    if catalog is None:
        raise HTTPException(409, "Candidate has no founder-approved discovery catalog.")
    data = candidate.document["data"]
    assets = [
        {
            "venue": data["venue"],
            "instrument": instrument,
            "timeframe": data["timeframe"],
        }
        for instrument in data["instruments"]
    ]
    task = build_task(
        TaskCreate(
            task_number=f"A7-DATA-{str(candidate.id)[:12]}",
            project="bulletproof_bt",
            task_type="alpha_data_admission",
            title=f"Admit selected panels: {', '.join(data['instruments'])}",
            objective=(
                "Content-hash and quality-check only the preregistered manifest-visible "
                "panels, retaining native no-authority admission receipts."
            ),
            priority=88,
            risk_level=0,
            created_by="alpha-continuous-director",
            input_contract={
                "repository": "bulletproof_bt",
                "workflow": "alpha-data-admission",
                "base_ref": mandate.specification["bulletproof_source_commit"],
                "candidate_id": str(candidate.id),
                "candidate_digest": candidate.candidate_digest,
                "catalog_receipt_id": catalog["producer_receipt_id"],
                "catalog_receipt_digest": catalog["receipt_digest"],
                "source_commit": mandate.specification["bulletproof_source_commit"],
                "data_root": "/home/omenka/Projects/bulletproof_bt/research_data",
                "backup_root": "/home/omenka/.local/share/invariance-swarm/alpha-data-backups",
                "assets": assets,
                "authority": "no_capital_data_admission",
            },
            expected_outputs=[
                "content-bound ALPHA-001 receipts for each selected panel",
                "verified content-addressed recovery copies",
            ],
            acceptance_criteria=[
                "only preregistered manifest-visible panels are read",
                "DATA-002/003 quality checks and exact bytes are retained",
                "no code, shadow, order, capital or promotion authority exists",
            ],
            approval_policy={
                "kind": "weekly_research_mandate",
                "mandate_digest": mandate.mandate_digest,
                "catalog_receipt_digest": catalog["receipt_digest"],
                "risk": 0,
            },
            approval_required=False,
            required_capabilities=[
                "alpha-data-admission",
                "market-data-read",
                "research-audit",
            ],
            allowed_machines=["vm1-developer"],
            max_attempts=3,
        )
    )
    persist_new_task(db, task)
    document = {
        "candidate_id": str(candidate.id),
        "candidate_digest": candidate.candidate_digest,
        "task_id": str(task.id),
        "catalog_receipt_id": catalog["producer_receipt_id"],
        "catalog_receipt_digest": catalog["receipt_digest"],
        "assets": assets,
        "authority": "no_capital_data_admission",
    }
    admission = AlphaCandidateDataAdmission(
        candidate_id=candidate.id,
        task_id=task.id,
        catalog_receipt_id=catalog["producer_receipt_id"],
        catalog_receipt_digest=catalog["receipt_digest"],
        assets=assets,
        status="queued",
        receipt_ids=[],
        dataset_bindings=[],
        failure={},
        record_digest=digest_document(document),
    )
    db.add(admission)
    db.flush()
    return admission


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
    campaign_bindings = [
        {key: value for key, value in binding.items() if key in _BINDING_KEYS}
        for binding in mandate.specification["dataset_bindings"]
    ]
    selected_instruments: list[str] = []
    selected_venues: list[str] = []
    for item in accepted:
        admission = db.scalar(
            select(AlphaCandidateDataAdmission).where(
                AlphaCandidateDataAdmission.candidate_id == item.id,
                AlphaCandidateDataAdmission.status == "admitted",
            )
        )
        admitted = admission.dataset_bindings if admission is not None else []
        for binding in admitted:
            if binding not in campaign_bindings:
                campaign_bindings.append(binding)
        data = item.document.get("data", {})
        selected_venues.append(str(data.get("venue", "")))
        selected_instruments.extend(data.get("instruments", []))
    campaign = register_campaign(
        db,
        AlphaCampaignCreate(
            campaign_key=f"ALPHA004-{str(mandate.id)[:8]}-{cycle.ordinal:03d}",
            version="1.0.0",
            project="bulletproof-bt",
            objective=mandate.objective,
            discovery_portfolio_id=portfolio.id,
            dataset_bindings=campaign_bindings,
            bulletproof_source_commit=mandate.specification[
                "bulletproof_source_commit"
            ],
            allowed_venues=sorted(
                set(
                    filter(
                        None,
                        [*mandate.specification["allowed_venues"], *selected_venues],
                    )
                )
            ),
            allowed_instruments=sorted(
                {*mandate.specification["allowed_instruments"], *selected_instruments}
            ),
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


def recover_discovery_grounding(db: Session, mandate, payload):
    moment = now()
    if mandate.status != "active" or not (
        mandate.valid_from <= moment < mandate.valid_until
    ):
        raise HTTPException(409, "Grounding recovery requires an active mandate.")
    if mandate.mandate_digest != payload.expected_mandate_digest:
        raise HTTPException(409, "Mandate digest changed before grounding recovery.")
    cycle = db.scalar(
        select(AlphaDiscoveryCycle)
        .where(AlphaDiscoveryCycle.mandate_id == mandate.id)
        .order_by(AlphaDiscoveryCycle.ordinal.desc())
        .limit(1)
    )
    if cycle is None or cycle.id != payload.expected_cycle_id:
        raise HTTPException(409, "Discovery cycle changed before grounding recovery.")
    if (
        cycle.status not in {"completed", "rejected", "needs_attention"}
        or cycle.campaign_id
    ):
        raise HTTPException(
            409, "Only a terminal ungrounded discovery cycle can be recovered."
        )
    if cycle.context.get("research_intelligence", {}).get("citations"):
        raise HTTPException(409, "Grounded discovery cannot use grounding recovery.")
    for task_id in (
        cycle.intelligence_task_id,
        cycle.hypothesis_task_id,
        cycle.representation_task_id,
    ):
        if task_id:
            task = db.get(Task, task_id)
            if task is None or task.status not in {"succeeded", "failed", "cancelled"}:
                raise HTTPException(409, "Discovery stage is still active.")
    if db.scalar(
        select(AlphaFounderResearchIdea).where(
            AlphaFounderResearchIdea.cycle_id == cycle.id
        )
    ):
        raise HTTPException(
            409, "Founder ideas require explicit new intake, not automatic recovery."
        )
    for consumed, limit in (
        (mandate.cycle_count, "maximum_cycles"),
        (mandate.hypothesis_count, "maximum_hypotheses"),
        (mandate.trial_count, "maximum_total_trials"),
    ):
        if consumed >= mandate.budget[limit]:
            raise HTTPException(409, "Mandate research budget is exhausted.")
    context = _bounded_context(db, mandate)
    if not context.get("research_intelligence", {}).get("citations"):
        raise HTTPException(409, "Grounding recovery still has no current citations.")
    recovered = _new_cycle(db, mandate, prepared_context=context)
    _event(
        db,
        mandate,
        "ungrounded_discovery_recovered_by_operator",
        {
            "actor": payload.actor,
            "reason": payload.reason,
            "previous_cycle_id": str(cycle.id),
            "previous_cycle_digest": cycle.cycle_digest,
            "new_cycle_id": str(recovered.id),
            "new_cycle_digest": recovered.cycle_digest,
            "automatic_cadence_unchanged": True,
        },
        recovered,
    )
    return recovered


def _recover_resumed_stage(db: Session, mandate, cycle) -> bool:
    if cycle.status != "needs_attention" or cycle.campaign_id:
        return False
    stage = {
        "intelligence_synthesis": "intelligence",
        "hypothesis_generation": "hypothesis",
        "representation_selection": "representation",
    }.get(cycle.phase)
    if stage is None:
        return False
    task = db.get(Task, getattr(cycle, f"{stage}_task_id"))
    if task is None or task.status not in {"queued", "leased", "running", "succeeded"}:
        return False
    contract = task.input_contract or {}
    if any(
        contract.get(key) != value
        for key, value in {
            "cycle_id": str(cycle.id),
            "mandate_id": str(mandate.id),
            "mandate_digest": mandate.mandate_digest,
            "stage": stage,
        }.items()
    ):
        return False
    failed = db.scalar(
        select(AlphaDiscoveryEvent)
        .where(
            AlphaDiscoveryEvent.cycle_id == cycle.id,
            AlphaDiscoveryEvent.event_type == f"{stage}_stage_failed",
        )
        .order_by(AlphaDiscoveryEvent.sequence.desc())
        .limit(1)
    )
    resumed = db.scalar(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id, TaskEvent.event_type == "task_resumed")
        .order_by(TaskEvent.id.desc())
        .limit(1)
    )
    if failed is None or resumed is None or resumed.created_at <= failed.created_at:
        return False
    cycle.status = "running"
    cycle.completed_at = None
    cycle.next_action = "await_recovered_discovery_stage"
    _event(
        db,
        mandate,
        "discovery_stage_resumed_by_operator",
        {
            "task_id": str(task.id),
            "task_resume_event_id": resumed.id,
            "requested_by": (resumed.payload or {}).get("requested_by"),
        },
        cycle,
    )
    return True


def _reconcile_data_admissions(
    db: Session,
    mandate: AlphaResearchMandate,
    cycle: AlphaDiscoveryCycle,
) -> bool:
    if cycle.status != "awaiting_data_admission":
        return False
    candidates = db.scalars(
        select(AlphaDiscoveryCandidate).where(
            AlphaDiscoveryCandidate.cycle_id == cycle.id
        )
    ).all()
    pending = [
        item for item in candidates if item.disposition == "awaiting_data_admission"
    ]
    if not pending:
        cycle.status = "running"
        _portfolio_and_campaign(
            db,
            mandate,
            cycle,
            [item for item in candidates if item.disposition == "accepted"],
        )
        return True
    active = False
    for candidate in pending:
        admission = db.scalar(
            select(AlphaCandidateDataAdmission).where(
                AlphaCandidateDataAdmission.candidate_id == candidate.id
            )
        )
        if admission is None:
            raise HTTPException(409, "Candidate admission ledger is missing.")
        if admission.status in {"admitted", "failed"}:
            continue
        task = db.get(Task, admission.task_id)
        if task is None:
            raise HTTPException(409, "Candidate admission task is missing.")
        if task.status in {"queued", "leased", "running", "pending_approval"}:
            admission.status = task.status
            active = True
            continue
        if task.status != "succeeded":
            admission.status = "failed"
            admission.failure = task.failure or {"category": "admission_task_failed"}
            admission.completed_at = now()
            continue
        document = task.result.get("summary", {}).get("alpha_data_admission", {})
        catalog = mandate.specification.get("discovery_catalog", {})
        if (
            document.get("schema_version")
            != "alpha007-selected-panel-admission-batch-v1.0.0"
            or document.get("candidate_id") != str(candidate.id)
            or document.get("candidate_digest") != candidate.candidate_digest
            or document.get("catalog_receipt_digest") != catalog.get("receipt_digest")
            or document.get("capital_or_order_authority") is not False
        ):
            raise HTTPException(409, "Selected-panel admission result changed scope.")
        receipts = document.get("receipts")
        if not isinstance(receipts, list) or len(receipts) != len(admission.assets):
            raise HTTPException(409, "Selected-panel admission receipt count changed.")
        expected = {
            (item["venue"], item["instrument"], item["timeframe"])
            for item in admission.assets
        }
        observed = {
            (
                item.get("result", {}).get("venue"),
                item.get("result", {}).get("instrument"),
                item.get("result", {}).get("timeframe"),
            )
            for item in receipts
        }
        if observed != expected:
            raise HTTPException(409, "Selected-panel admission assets changed.")
        bindings = [
            register_selected_panel_receipt(
                db,
                receipt_document=receipt,
                registered_at=task.completed_at or now(),
            ).model_dump(mode="json")
            for receipt in receipts
        ]
        admission.status = "admitted"
        admission.receipt_ids = [item["producer_receipt_id"] for item in bindings]
        admission.dataset_bindings = bindings
        admission.completed_at = now()
        _event(
            db,
            mandate,
            "candidate_data_admitted",
            {
                "candidate_id": str(candidate.id),
                "task_id": str(task.id),
                "dataset_bindings": bindings,
                "execution_authority": False,
            },
            cycle,
        )
    if active:
        cycle.next_action = "await_selected_panel_admission"
        return True
    cycle.status = "running"
    admitted_candidate_ids = set(
        db.scalars(
            select(AlphaCandidateDataAdmission.candidate_id).where(
                AlphaCandidateDataAdmission.candidate_id.in_(
                    [item.id for item in candidates]
                ),
                AlphaCandidateDataAdmission.status == "admitted",
            )
        ).all()
    )
    accepted = [
        item
        for item in candidates
        if item.disposition == "accepted" or item.id in admitted_candidate_ids
    ]
    cycle.metrics = {
        **cycle.metrics,
        "accepted": len(accepted),
        "awaiting_data_admission": 0,
        "rejected": len(candidates) - len(accepted),
    }
    _portfolio_and_campaign(db, mandate, cycle, accepted)
    return True


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
        elif campaign and campaign.status == "cancelled":
            if cycle.status != "rejected":
                cycle.status = "rejected"
                cycle.phase = "complete"
                cycle.next_action = "schedule_next_discovery_cycle"
                cycle.completed_at = moment
                _event(
                    db,
                    mandate,
                    "campaign_cancelled_without_candidate",
                    {
                        "campaign_id": str(campaign.id),
                        "terminal_reason": campaign.terminal_reason,
                        "hypotheses": campaign.hypothesis_count,
                        "trials": campaign.trial_count,
                    },
                    cycle,
                )
        if campaign is None or campaign.status != "cancelled":
            return
    if _reconcile_data_admissions(db, mandate, cycle):
        return
    _recover_resumed_stage(db, mandate, cycle)
    if cycle.status in _TERMINAL_CYCLE:
        founder_idea = db.scalar(
            select(AlphaFounderResearchIdea).where(
                AlphaFounderResearchIdea.cycle_id == cycle.id
            )
        )
        if founder_idea and founder_idea.status == "processing":
            founder_idea.status = (
                "completed" if cycle.status == "completed" else cycle.status
            )
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
    if not isinstance(raw, list):
        cycle.status = "needs_attention"
        cycle.next_action = "review_invalid_hypothesis_output"
        return
    if cycle.representation_task_id is None:
        task = _task(
            db,
            mandate,
            cycle,
            "representation",
            {
                **cycle.context,
                "research_brief": brief,
                "raw_candidates": raw,
                "outcome_data_available": False,
            },
        )
        cycle.representation_task_id = task.id
        cycle.phase = "representation_selection"
        cycle.next_action = "await_data_representation_agent"
        _event(
            db,
            mandate,
            "representation_task_created",
            {"task_id": str(task.id), "candidate_count": len(raw)},
            cycle,
        )
        return
    representation = db.get(Task, cycle.representation_task_id)
    if representation is None or representation.status not in {
        "succeeded",
        "failed",
        "cancelled",
    }:
        return
    if representation.status != "succeeded":
        cycle.status = "needs_attention"
        cycle.next_action = "repair_data_representation_agent"
        _event(
            db,
            mandate,
            "representation_stage_failed",
            {"task_id": str(representation.id)},
            cycle,
        )
        return
    raw_plans = (
        representation.result.get("summary", {})
        .get("alpha_discovery_output", {})
        .get("representation_plans", [])
    )
    try:
        represented, representation_brief = _apply_representation_plans(
            raw, raw_plans if isinstance(raw_plans, list) else []
        )
    except (ValidationError, ValueError) as exc:
        cycle.status = "needs_attention"
        cycle.next_action = "review_invalid_representation_output"
        _event(
            db,
            mandate,
            "representation_output_rejected",
            {"task_id": str(representation.id), "detail": str(exc)[:2000]},
            cycle,
        )
        return
    cycle.representation_brief = representation_brief
    records = _materialize_candidates(db, mandate, cycle, represented)
    accepted = [item for item in records if item.disposition == "accepted"]
    awaiting_data = [
        item for item in records if item.disposition == "awaiting_data_admission"
    ]
    cycle.metrics = {
        "generated": len(records),
        "accepted": len(accepted),
        "awaiting_data_admission": len(awaiting_data),
        "rejected": len(records) - len(accepted) - len(awaiting_data),
        "duplicated": sum(
            bool(
                {"duplicate_prior_question", "semantic_duplicate_prior_question"}
                & set(item.reason_codes)
            )
            for item in records
        ),
    }
    if awaiting_data:
        cycle.status = "awaiting_data_admission"
        cycle.phase = "data_admission"
        cycle.next_action = "admit_selected_manifest_panels"
        _event(
            db,
            mandate,
            "candidate_data_admission_required",
            {
                "candidate_ids": [str(item.id) for item in awaiting_data],
                "candidate_digests": [item.candidate_digest for item in awaiting_data],
                "catalog_receipt_digest": mandate.specification.get(
                    "discovery_catalog", {}
                ).get("receipt_digest"),
                "execution_authority": False,
            },
            cycle,
        )
        return
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
                    "vm1-alpha-data-representation-scientist",
                    "vm1-alpha-research-executor-v2",
                    "vm1-alpha-research-executor-capacity-2",
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
                "representation_task_id": (
                    str(item.representation_task_id)
                    if item.representation_task_id
                    else None
                ),
                "representation_count": len(item.representation_brief or {}),
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
