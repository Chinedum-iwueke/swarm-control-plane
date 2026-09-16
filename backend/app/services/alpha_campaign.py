from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.alpha_campaign import (
    AlphaCampaign,
    AlphaCampaignAttempt,
    AlphaCampaignEvent,
)
from app.models.alpha_discovery import (
    AlphaCandidateDataAdmission,
    AlphaDiscoveryCandidate,
    AlphaResearchMandate,
)
from app.models.data_contract import ResearchDatasetBuild, ResearchDatasetManifest
from app.models.discovery_portfolio import (
    DiscoveryPortfolio,
    DiscoveryPortfolioCandidate,
)
from app.models.evaluator_routing import (
    EvaluationRoute,
    EvaluatorAssignment,
    EvaluatorProfile,
)
from app.models.governance import FounderNotification, TaskApproval
from app.models.lake_operations import LakeGovernanceSnapshot
from app.models.market_data_catalog import MarketDataCatalogSnapshot
from app.models.quantitative_receipt import QuantitativeProducerReceipt
from app.models.research_bridge import GovernedResearchBridge
from app.models.task import Task
from app.schemas.alpha_campaign import (
    AlphaCampaignAction,
    AlphaCampaignActivation,
    AlphaCampaignAttemptCreate,
    AlphaCampaignCreate,
)
from app.schemas.evaluator_routing import EvaluationRouteCreate, ProducerIdentity
from app.schemas.task import TaskCreate
from app.services.evaluator_routing import (
    alpha_strategy_reviews_approved,
    create_route,
    require_independence,
    retry_blocked_route,
    task_producer_identity,
)
from app.services.governance import consume_task_approval
from app.services.graph import digest_document
from app.services.tasks import append_task_event, build_task, persist_new_task

TERMINAL = {
    "shadow_candidate",
    "completed_no_candidate",
    "needs_attention",
    "cancelled",
}
CLAIM_BOUNDARY = (
    "ALPHA-001 coordinates no-capital research only. Bulletproof is the quantitative "
    "producer; candidate status permits prospective shadow review, never orders, "
    "capital allocation, production promotion or self-approval."
)


def now() -> datetime:
    return datetime.now(UTC)


def _append_event(
    db: Session, campaign: AlphaCampaign, kind: str, actor: str, payload: dict
) -> AlphaCampaignEvent:
    prior = db.scalar(
        select(AlphaCampaignEvent)
        .where(AlphaCampaignEvent.campaign_id == campaign.id)
        .order_by(AlphaCampaignEvent.sequence.desc())
        .limit(1)
    )
    sequence = (prior.sequence if prior else 0) + 1
    previous = prior.event_digest if prior else None
    document = {
        "campaign_id": str(campaign.id),
        "sequence": sequence,
        "event_type": kind,
        "actor": actor,
        "payload": payload,
        "previous_digest": previous,
    }
    event = AlphaCampaignEvent(
        campaign_id=campaign.id,
        sequence=sequence,
        event_type=kind,
        actor=actor,
        payload=payload,
        previous_digest=previous,
        event_digest=digest_document(document),
    )
    db.add(event)
    db.flush()
    return event


def validate_real_data_bindings(
    db: Session, payload: AlphaCampaignCreate
) -> list[dict]:
    admitted: list[dict] = []
    allowed_venues = set(payload.allowed_venues)
    allowed_instruments = {item.upper() for item in payload.allowed_instruments}
    forbidden_markers = {"synthetic", "fixture", "mock", "example", "test-data"}
    seen_builds: set = set()
    for binding in payload.dataset_bindings:
        if binding.dataset_build_id in seen_builds:
            raise HTTPException(422, "A dataset build may be bound only once.")
        seen_builds.add(binding.dataset_build_id)
        build = db.get(ResearchDatasetBuild, binding.dataset_build_id)
        manifest_record = (
            db.get(ResearchDatasetManifest, build.manifest_id) if build else None
        )
        catalog = db.get(MarketDataCatalogSnapshot, binding.catalog_id)
        lake = db.get(LakeGovernanceSnapshot, binding.lake_governance_snapshot_id)
        producer_receipt = db.get(
            QuantitativeProducerReceipt, binding.producer_receipt_id
        )
        if not all((build, manifest_record, catalog, lake, producer_receipt)):
            raise HTTPException(
                422,
                "Every real-data binding requires existing build, manifest, catalog, lake governance and Bulletproof admission records.",
            )
        manifest = manifest_record.manifest
        provider = manifest.get("provider", {})
        venue = str(provider.get("venue", "")).lower()
        identity = " ".join(
            str(provider.get(key, "")).lower() for key in ("name", "dataset", "venue")
        )
        uris = [
            str(item.get("uri", "")).lower()
            for item in manifest.get("source_objects", [])
        ]
        if venue not in allowed_venues or any(
            marker in identity for marker in forbidden_markers
        ):
            raise HTTPException(
                422,
                "Campaign data must identify an allowed live exchange and cannot be synthetic or fixture data.",
            )
        if any(any(marker in uri for marker in forbidden_markers) for uri in uris):
            raise HTTPException(
                422,
                "Campaign source URIs cannot identify synthetic, fixture or test data.",
            )
        if build.builder_repository not in {"bulletproof_bt", "bulletproof-bt"}:
            raise HTTPException(
                422, "The immutable dataset build must be produced by Bulletproof."
            )
        receipt = producer_receipt.receipt
        admission = receipt.get("result", {})
        if (
            producer_receipt.milestone != "ALPHA-001"
            or producer_receipt.dataset_digest != build.content_digest
            or producer_receipt.source_commit != payload.bulletproof_source_commit
            or not producer_receipt.producer.startswith("bt.")
            or admission.get("evidence_class") != "live_exchange_history"
            or admission.get("admitted") is not True
            or str(admission.get("venue", "")).lower() != venue
            or str(admission.get("instrument", "")).upper() not in allowed_instruments
            or any(receipt.get("authority", {}).values())
        ):
            raise HTTPException(
                422,
                "Bulletproof real-data admission receipt does not match the frozen dataset or authority boundary.",
            )
        if provider.get("dataset") != binding.dataset_key:
            raise HTTPException(
                422, "Dataset binding key does not match its immutable manifest."
            )
        manifest_instruments = {
            str(item).upper() for item in manifest.get("instruments", [])
        }
        if not manifest_instruments or not manifest_instruments.issubset(
            allowed_instruments
        ):
            raise HTTPException(
                422, "Dataset instruments exceed the frozen campaign scope."
            )
        if lake.catalog_digest != catalog.catalog_digest:
            raise HTTPException(
                422, "Lake governance does not bind the selected market-data catalog."
            )
        partitions = {
            item["content_digest"]: item
            for item in catalog.catalog.get("partitions", [])
            if item.get("dataset_key") == binding.dataset_key
        }
        selected = [partitions.get(item) for item in binding.partition_digests]
        if any(item is None for item in selected):
            raise HTTPException(
                422,
                "A bound partition is absent from the immutable market-data catalog.",
            )
        if build.content_digest not in binding.partition_digests:
            raise HTTPException(
                422,
                "The bound catalog partitions do not contain the admitted panel digest.",
            )
        if any(
            item.get("layer") != "curated"
            or str(item.get("venue_id", "")).lower() != venue
            or item.get("duplicate_count") != 0
            or item.get("gap_count") != 0
            or item.get("access_mode") != "read_only"
            for item in selected
        ):
            raise HTTPException(
                422,
                "Campaign partitions must be curated, read-only, gap-free, duplicate-free and venue-consistent.",
            )
        available_sources = {
            item.get("source_key")
            for item in catalog.catalog.get("source_availability", [])
            if item.get("status") == "available"
        }
        if any(item.get("source_key") not in available_sources for item in selected):
            raise HTTPException(
                422, "A campaign partition lacks an available source ledger entry."
            )
        snapshot = lake.snapshot
        quality = next(
            (
                item
                for item in snapshot.get("quality_slos", [])
                if item.get("dataset_key") == binding.dataset_key
                and item.get("layer") == "curated"
            ),
            None,
        )
        entitlement = next(
            (
                item
                for item in snapshot.get("entitlements", [])
                if item.get("principal") == binding.research_principal
                and binding.dataset_key in item.get("dataset_keys", [])
                and "read" in item.get("actions", [])
                and item.get("purpose") == "research"
            ),
            None,
        )
        if quality is None or entitlement is None:
            raise HTTPException(
                422,
                "Real-data research requires a curated quality SLO and an explicit read-only research entitlement.",
            )
        admitted.append(
            {
                **binding.model_dump(mode="json"),
                "dataset_digest": build.content_digest,
                "manifest_digest": manifest_record.manifest_digest,
                "catalog_digest": catalog.catalog_digest,
                "lake_governance_digest": lake.snapshot_digest,
                "venue": venue,
                "instruments": sorted(manifest_instruments),
                "output_columns": manifest.get("output_columns", []),
                "rows": build.rows,
                "builder_commit": build.builder_commit,
                "producer_receipt_digest": producer_receipt.receipt_digest,
            }
        )
    return admitted


def register_campaign(db: Session, payload: AlphaCampaignCreate) -> AlphaCampaign:
    portfolio = db.get(DiscoveryPortfolio, payload.discovery_portfolio_id)
    if (
        portfolio is None
        or portfolio.project != payload.project
        or portfolio.status != "allocated"
        or portfolio.selected_count < 1
    ):
        raise HTTPException(
            422,
            "Campaign requires an allocated discovery portfolio with a selected inquiry.",
        )
    admitted = validate_real_data_bindings(db, payload)
    selected = db.scalars(
        select(DiscoveryPortfolioCandidate)
        .where(
            (DiscoveryPortfolioCandidate.portfolio_id == portfolio.id)
            & (DiscoveryPortfolioCandidate.selected.is_(True))
        )
        .order_by(DiscoveryPortfolioCandidate.rank)
    ).all()
    if len(selected) != portfolio.selected_count:
        raise HTTPException(
            409,
            "Discovery portfolio selection is incomplete or internally inconsistent.",
        )
    if payload.budget.max_hypotheses < len(selected):
        raise HTTPException(
            422, "Campaign hypothesis budget cannot cover its selected research queue."
        )
    specification = payload.model_dump(
        mode="json",
        exclude={"budget", "created_by", "dataset_bindings"},
        exclude_none=True,
    )
    specification["dataset_bindings"] = admitted
    specification["discovery_allocation_digest"] = portfolio.allocation_digest
    research_queue = []
    for item in selected:
        entry = {
            "source_candidate_id": str(item.id),
            "source_candidate_digest": item.candidate_digest,
            "question": item.question,
            "domain_key": item.domain_key,
            "rank": item.rank,
        }
        if getattr(item, "source_type", None) == "alpha_discovery_candidate":
            source = db.get(AlphaDiscoveryCandidate, item.source_id)
            if source is None or source.candidate_digest != item.source_digest:
                raise HTTPException(409, "ALPHA-004 source candidate is unavailable.")
            binding_index = source.document["dataset_binding_index"]
            binding_indices = []
            if binding_index is None:
                admission = db.scalar(
                    select(AlphaCandidateDataAdmission).where(
                        AlphaCandidateDataAdmission.candidate_id == source.id,
                        AlphaCandidateDataAdmission.status == "admitted",
                    )
                )
                if admission is None:
                    raise HTTPException(
                        409, "ALPHA-004 candidate data admission is incomplete."
                    )
                for binding in admission.dataset_bindings:
                    index = next(
                        (
                            position
                            for position, admitted_binding in enumerate(admitted)
                            if admitted_binding["dataset_build_id"]
                            == binding["dataset_build_id"]
                        ),
                        None,
                    )
                    if index is None:
                        raise HTTPException(
                            409, "Admitted candidate dataset is absent from the campaign."
                        )
                    binding_indices.append(index)
                binding_index = binding_indices[0]
            else:
                binding_indices = [int(binding_index)]
            entry["dataset_binding_index"] = int(binding_index)
            entry["dataset_binding_indices"] = binding_indices
            entry["instrument"] = source.document["data"]["instrument"]
            entry["instruments"] = source.document["data"]["instruments"]
            entry["research_timeframe"] = source.document["data"][
                "research_timeframe"
            ]
            entry["resampling_policy"] = source.document["data"][
                "resampling_policy"
            ]
            entry["reusable_strategy"] = source.document.get(
                "reusable_strategy_capability"
            )
            entry["discovery_candidate_id"] = str(source.id)
            entry["discovery_candidate_digest"] = source.candidate_digest
        research_queue.append(entry)
    specification["research_queue"] = research_queue
    specification["authority_boundary"] = {
        "capital": False,
        "orders": False,
        "production_promotion": False,
        "self_approval": False,
    }
    campaign_digest = digest_document(
        {
            "specification": specification,
            "budget": payload.budget.model_dump(mode="json"),
        }
    )
    existing = db.scalar(
        select(AlphaCampaign).where(
            (AlphaCampaign.campaign_key == payload.campaign_key)
            & (AlphaCampaign.version == payload.version)
        )
    )
    if existing is not None:
        if existing.campaign_digest != campaign_digest:
            raise HTTPException(
                409, "Campaign key and version are already bound to different content."
            )
        return existing
    campaign = AlphaCampaign(
        campaign_key=payload.campaign_key,
        version=payload.version,
        project=payload.project,
        objective=payload.objective,
        discovery_portfolio_id=payload.discovery_portfolio_id,
        campaign_digest=campaign_digest,
        specification=specification,
        budget=payload.budget.model_dump(mode="json"),
        status="awaiting_activation",
        phase="approval",
        next_action="founder_activation",
        terminal_reason={},
        created_by=payload.created_by,
        heartbeat_at=now(),
    )
    db.add(campaign)
    db.flush()
    _append_event(
        db,
        campaign,
        "campaign_registered",
        payload.created_by,
        {
            "campaign_digest": campaign_digest,
            "discovery_allocation_digest": portfolio.allocation_digest,
            "dataset_digests": [item["dataset_digest"] for item in admitted],
            "authority": "no_capital",
        },
    )
    return campaign


def activate_campaign(
    db: Session, campaign: AlphaCampaign, payload: AlphaCampaignActivation
) -> None:
    if campaign.status != "awaiting_activation":
        raise HTTPException(409, "Only an awaiting campaign can be activated.")
    if campaign.campaign_digest != payload.expected_campaign_digest:
        raise HTTPException(409, "Campaign digest changed before activation.")
    if payload.actor == "alpha-continuous-director":
        if campaign.specification.get("execution_protocol") != "alpha004-delegated-v1":
            raise HTTPException(403, "Director activation requires ALPHA-004 protocol.")
        mandate = db.get(
            AlphaResearchMandate, campaign.specification.get("research_mandate_id")
        )
        if (
            mandate is None
            or mandate.status != "active"
            or mandate.mandate_digest
            != campaign.specification.get("research_mandate_digest")
            or not (mandate.valid_from <= now() < mandate.valid_until)
        ):
            raise HTTPException(
                403, "Weekly research mandate is absent, expired or changed."
            )
    campaign.status = "running"
    campaign.phase = "hypothesis"
    campaign.next_action = "compile_evidence_grounded_hypothesis"
    campaign.activated_at = campaign.heartbeat_at = now()
    _append_event(
        db,
        campaign,
        "campaign_activated",
        payload.actor,
        {
            "reason": payload.reason,
            "campaign_digest": campaign.campaign_digest,
            "authority": "no_capital",
        },
    )
    _ensure_execution_task(db, campaign)


def _execution_task_number(campaign: AlphaCampaign, source: dict) -> str:
    return f"A2-{str(campaign.id)[:8]}-{int(source['rank']):03d}"


def _stage_task_number(campaign: AlphaCampaign, source: dict, stage: str) -> str:
    return f"A3-{str(campaign.id)[:8]}-{int(source['rank']):03d}-{stage}"


def _stage_contract(
    db: Session,
    campaign: AlphaCampaign,
    source: dict,
    *,
    stage: str,
    hypothesis_card: dict | None = None,
    card_approval: dict | None = None,
    qualification: dict | None = None,
) -> dict:
    bindings = _source_bindings(campaign, source)
    binding = bindings[0]
    question = " ".join(source["question"].split())
    return {
        "repository": "bulletproof_bt",
        "workflow": "alpha-research-execution",
        "base_ref": campaign.specification["bulletproof_source_commit"],
        "campaign_id": str(campaign.id),
        "campaign_digest": campaign.campaign_digest,
        "source_candidate_id": source["source_candidate_id"],
        "source_candidate_digest": source["source_candidate_digest"],
        "question": question,
        "question_digest": digest_document({"question": question}),
        "domain_key": source["domain_key"],
        "dataset_build_id": binding["dataset_build_id"],
        "dataset_digest": binding["dataset_digest"],
        "dataset_path": _dataset_path(db, campaign, binding),
        "memory_database": "/home/omenka/.local/state/invariance-swarm/alpha002-memory.sqlite",
        "bundle_root": "/home/omenka/.local/share/invariance-swarm/alpha002-bundles",
        "dataset_key": binding["dataset_key"],
        "dataset_bindings": [
            {
                "dataset_build_id": item["dataset_build_id"],
                "dataset_digest": item["dataset_digest"],
                "dataset_path": _dataset_path(db, campaign, item),
                "dataset_key": item["dataset_key"],
                "instrument": item.get(
                    "instruments",
                    [
                        source.get(
                            "instrument",
                            campaign.specification["allowed_instruments"][0],
                        )
                    ],
                )[0],
                "venue": item["venue"],
            }
            for item in bindings
        ],
        "instrument": source.get(
            "instrument", campaign.specification["allowed_instruments"][0]
        ),
        "instruments": source.get(
            "instruments",
            [source.get("instrument", campaign.specification["allowed_instruments"][0])],
        ),
        "timeframe": "1m",
        "research_timeframe": source.get("research_timeframe", "1m"),
        "resampling_policy": source.get(
            "resampling_policy", "right_closed_left_labeled_complete_bars"
        ),
        "reusable_strategy": source.get("reusable_strategy"),
        "tier": "Tier2B",
        "max_variants": campaign.budget["max_variants_per_hypothesis"],
        "research_context": _research_context(db, question),
        "authority": "no_capital",
        "stage": stage,
        "venue": binding["venue"],
        "window_start": campaign.specification["execution_window_start"],
        "window_end": campaign.specification["execution_window_end"],
        **({"hypothesis_card": hypothesis_card} if hypothesis_card else {}),
        **({"card_approval": card_approval} if card_approval else {}),
        **({"qualification": qualification} if qualification else {}),
    }


def _source_bindings(campaign: AlphaCampaign, source: dict) -> list[dict]:
    indices = source.get("dataset_binding_indices")
    if indices is None:
        indices = [source.get("dataset_binding_index", 0)]
    if not isinstance(indices, list) or not indices:
        raise HTTPException(409, "Research queue has no admitted dataset bindings.")
    try:
        bindings = [campaign.specification["dataset_bindings"][int(item)] for item in indices]
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(409, "Research queue dataset bindings changed.") from exc
    if len({item["dataset_build_id"] for item in bindings}) != len(bindings):
        raise HTTPException(409, "Research queue dataset bindings are duplicated.")
    return bindings


def _research_context(db: Session, question: str) -> dict:
    from app.schemas.retrieval import HybridRetrievalRequest
    from app.services.evidence import ORCHESTRATOR_ACCESS
    from app.services.retrieval import hybrid_search

    try:
        result = hybrid_search(
            db, HybridRetrievalRequest(query=question, limit=5), ORCHESTRATOR_ACCESS
        )
        return {
            "corpus_digest": result["corpus_digest"],
            "abstained": result["abstained"],
            "citations": [
                {
                    "object_id": str(hit["object_id"]),
                    "content_digest": hit["citation"]["content_digest"],
                    "coordinates": hit["citation"]["coordinates"],
                    "text": hit["text"][:1200],
                    "confidence": hit["confidence"],
                }
                for hit in result["hits"]
            ],
        }
    except HTTPException as exc:
        return {
            "corpus_digest": None,
            "abstained": True,
            "citations": [],
            "error": str(exc.detail),
        }


def _create_stage_task(
    db: Session,
    campaign: AlphaCampaign,
    source: dict,
    *,
    suffix: str,
    title: str,
    contract: dict,
    approval_required: bool,
) -> Task:
    task = build_task(
        TaskCreate(
            task_number=_stage_task_number(campaign, source, suffix),
            project="bulletproof_bt",
            task_type="alpha_research_execution",
            title=title,
            objective="Advance one selected real-data hypothesis through the governed Bulletproof research bridge without capital or order authority.",
            priority=90,
            risk_level=0,
            created_by="alpha-campaign-director",
            input_contract=contract,
            expected_outputs=["digest-bound hypothesis or execution evidence"],
            acceptance_criteria=[
                "exact question, dataset, window, tier and grid remain immutable",
                "classic Bulletproof and truth gates remain authoritative",
                "no capital, order, promotion or self-approval authority exists",
            ],
            approval_policy={
                "kind": "explicit" if approval_required else "registry_gate",
                "risk": 0,
                "campaign_digest": campaign.campaign_digest,
            },
            approval_required=approval_required,
            required_capabilities=(
                ["founder-confirmation"]
                if suffix == "C"
                else ["alpha-research-execution", "backtesting", "research-audit"]
            ),
            allowed_machines=["vm1-developer"],
            max_attempts=3,
        )
    )
    persist_new_task(db, task)
    return task


def _create_strategy_engineering_task(
    db: Session,
    campaign: AlphaCampaign,
    source: dict,
    requirement: dict,
) -> Task:
    question = " ".join(source["question"].split())
    bindings = _source_bindings(campaign, source)
    binding = bindings[0]
    research_context = _research_context(db, question)
    candidate_document = None
    if source.get("discovery_candidate_id"):
        candidate = db.get(AlphaDiscoveryCandidate, source["discovery_candidate_id"])
        if (
            candidate is None
            or candidate.candidate_digest != source["discovery_candidate_digest"]
            or " ".join(candidate.question.split()) != question
        ):
            raise HTTPException(
                409, "Engineering discovery evidence is absent or changed."
            )
        candidate_document = candidate.document
    evidence = {
        "schema_version": "alpha-strategy-engineering-evidence-v1.0.0",
        "campaign_digest": campaign.campaign_digest,
        "question": question,
        "question_digest": digest_document({"question": question}),
        "source_candidate_id": source["source_candidate_id"],
        "source_candidate_digest": source["source_candidate_digest"],
        "discovery_candidate": candidate_document,
        "dataset_binding": binding,
        "dataset_bindings": bindings,
        "instrument": source.get(
            "instrument", campaign.specification["allowed_instruments"][0]
        ),
        "instruments": source.get(
            "instruments",
            [source.get("instrument", campaign.specification["allowed_instruments"][0])],
        ),
        "research_timeframe": source.get("research_timeframe", "1m"),
        "resampling_policy": source.get(
            "resampling_policy", "right_closed_left_labeled_complete_bars"
        ),
        "window": {
            "start": campaign.specification["execution_window_start"],
            "end": campaign.specification["execution_window_end"],
        },
        "maximum_variants": campaign.budget["max_variants_per_hypothesis"],
        "tier": "Tier2B",
        "research_context": research_context,
        "engineering_requirement": requirement,
        "authority": campaign.specification["authority_boundary"],
    }
    from app.schemas.proposal import ProposalEngineeringMissionContract

    contract = {
        "repository": "bulletproof_bt",
        "workflow": "engineering-mission",
        "base_ref": campaign.specification["bulletproof_source_commit"],
        "milestone_id": "ALPHA-003",
        "work_item_id": f"strategy-{source['source_candidate_id'][:12]}",
        "objective": (
            "Implement a causal native Bulletproof hypothesis card, YAML contract, and "
            f"strategy for this admitted Research Intelligence question: {question}"
        ),
        "allowed_paths": [
            "research/hypotheses",
            "src/bt/strategy",
            "tests",
            "src/bt/governance/alpha_strategy_pipeline.py",
            "scripts/run_alpha_research_assignment.py",
        ],
        "evidence_context": json.dumps(evidence, sort_keys=True, allow_nan=False),
        "context_paths": [
            "docs/HYPOTHESIS_STRATEGY_GENERATION_PROMPT.md",
            "src/bt/governance/alpha_strategy_pipeline.py",
            "scripts/run_alpha_research_assignment.py",
        ],
        "acceptance_criteria": [
            "The exact Research Intelligence question is represented without proxy substitution.",
            "The hypothesis YAML declares immutable data, window, tier, grid, costs, falsification and logging contracts.",
            "The native strategy uses only point-in-time inputs and passes causality, leakage, schema and independent-review gates.",
            "Tests cover deterministic compilation and execution while retaining negative, invalid and failed outcomes.",
            "The existing native draft/qualification runner discovers the generated card without mapping its question to a different template.",
            "No capital, order, promotion or self-approval authority is introduced.",
        ],
        "stop_conditions": [
            "Required market data is not admitted by DATA-002/003.",
            "The question cannot be represented without look-ahead or proxy substitution.",
            "The requested change exceeds the bounded file or diff budget.",
        ],
        "max_files_changed": 12,
        "max_diff_lines": 1800,
        "max_duration_seconds": 7200,
        "engineering_requirement": requirement,
        "research_context": research_context,
    }
    # The engineering worker contract forbids undeclared fields. Preserve the
    # diagnostic in the task evidence while keeping its executable input typed.
    executable_contract = {
        key: value
        for key, value in contract.items()
        if key not in {"engineering_requirement", "research_context"}
    }
    ProposalEngineeringMissionContract.model_validate(executable_contract)
    task = build_task(
        TaskCreate(
            task_number=_stage_task_number(campaign, source, "G"),
            project="bulletproof_bt",
            task_type="engineering_mission",
            title=f"Engineer native strategy: {question[:120]}",
            objective=executable_contract["objective"],
            priority=88,
            risk_level=1,
            created_by="alpha-campaign-director",
            input_contract=executable_contract,
            expected_outputs=["patch", "validation", "review", "pr_bundle"],
            acceptance_criteria=executable_contract["acceptance_criteria"],
            approval_policy={
                "kind": "explicit",
                "campaign_digest": campaign.campaign_digest,
                "engineering_requirement": requirement,
                "research_context": contract["research_context"],
            },
            approval_required=True,
            required_capabilities=["git", "python", "testing"],
            allowed_machines=["vm1-developer"],
            max_attempts=2,
        )
    )
    persist_new_task(db, task)
    return task


def _materialize_strategy_review_tasks(
    db: Session, route: EvaluationRoute, subject: dict, qualification: dict,
) -> None:
    if route.status != "assigned":
        return
    assignments = db.scalars(select(EvaluatorAssignment).where(
        EvaluatorAssignment.route_id == route.id, EvaluatorAssignment.status == "assigned",
    )).all()
    for assignment in assignments:
        profile = db.get(EvaluatorProfile, assignment.evaluator_profile_id)
        if profile is None:
            raise HTTPException(409, "Routed strategy reviewer profile is missing.")
        number = f"AR-{assignment.id}"
        if db.scalar(select(Task).where(Task.task_number == number)) is not None:
            continue
        task = build_task(TaskCreate(
            task_number=number, project="bulletproof-bt", task_type="alpha_strategy_review",
            title=f"Independent {assignment.review_kind} review",
            objective="Review the exact frozen native card/implementation; retain explicit findings without execution authority.",
            risk_level=0, created_by="alpha-campaign-director", max_attempts=2,
            required_capabilities=[f"alpha-strategy-review:{assignment.review_kind}"],
            allowed_machines=[profile.machine],
            input_contract={
                "repository": "bulletproof_bt", "workflow": "alpha-strategy-review",
                "base_ref": subject["source_commit"], "route_id": str(route.id),
                "assignment_id": str(assignment.id), "evaluator_agent_id": str(profile.agent_id),
                "evaluator_profile_digest": profile.profile_digest,
                "evaluator_package_digest": profile.package_digest,
                "review_kind": assignment.review_kind, "subject_digest": route.subject_digest,
                "subject": deepcopy(subject), "qualification": deepcopy(qualification),
                "max_duration_seconds": 900, "authority": "review_only_no_execution",
            },
            expected_outputs=["typed strategy review verdict", "retained review logs"],
            acceptance_criteria=["Exact subject/source binding", "No producer self-review", "No execution authority"],
        ))
        persist_new_task(db, task)


def _advance_governed_pipeline(db: Session, campaign: AlphaCampaign) -> Task | None:
    delegated = (
        campaign.specification.get("execution_protocol") == "alpha004-delegated-v1"
    )
    if delegated:
        mandate = db.get(
            AlphaResearchMandate, campaign.specification.get("research_mandate_id")
        )
        if (
            mandate is None
            or mandate.status != "active"
            or mandate.mandate_digest
            != campaign.specification.get("research_mandate_digest")
            or not (mandate.valid_from <= now() < mandate.valid_until)
        ):
            campaign.status = "needs_attention"
            campaign.next_action = "renew_weekly_research_mandate"
            campaign.terminal_reason = {"category": "research_mandate_unavailable"}
            return None
    queue = campaign.specification["research_queue"]
    if campaign.hypothesis_count >= len(queue):
        return None
    source = queue[campaign.hypothesis_count]
    draft = db.scalar(
        select(Task).where(
            Task.task_number == _stage_task_number(campaign, source, "D")
        )
    )
    if draft is None:
        campaign.phase = "hypothesis_draft"
        campaign.next_action = "draft_evidence_grounded_hypothesis"
        return _create_stage_task(
            db,
            campaign,
            source,
            suffix="D",
            title="Draft an evidence-grounded hypothesis card",
            contract=_stage_contract(db, campaign, source, stage="draft"),
            approval_required=False,
        )
    if draft.status != "succeeded":
        campaign.phase = "hypothesis_draft"
        campaign.next_action = "await_vm1_hypothesis_drafter"
        return draft
    summary = draft.result.get("summary", {})
    card = summary.get("hypothesis_card")
    if not isinstance(card, dict):
        requirement = summary.get(
            "engineering_requirement", {"category": "hypothesis_draft_missing"}
        )
        engineering = db.scalar(
            select(Task).where(
                Task.task_number == _stage_task_number(campaign, source, "G")
            )
        )
        if engineering is None:
            engineering = _create_strategy_engineering_task(
                db, campaign, source, requirement
            )
        campaign.phase = "strategy_engineering"
        if engineering.status == "pending_approval":
            campaign.next_action = "founder_strategy_engineering_approval"
        elif engineering.status in {"queued", "in_progress"}:
            campaign.next_action = "await_bounded_strategy_engineering"
        elif engineering.status == "succeeded":
            campaign.status = "needs_attention"
            campaign.next_action = "founder_merge_strategy_and_rebind_source_commit"
            campaign.terminal_reason = {
                "category": "strategy_engineering_completed",
                "task_id": str(engineering.id),
                "result": engineering.result,
            }
        else:
            campaign.status = "needs_attention"
            campaign.next_action = "strategy_engineering_failed"
            campaign.terminal_reason = {
                "category": "strategy_engineering_failed",
                "task_id": str(engineering.id),
                "status": engineering.status,
                "result": engineering.result,
            }
        return engineering
    if delegated:
        approval_receipt = {
            "actor": mandate.approved_by,
            "approved_at": mandate.approved_at.isoformat(),
            "plan_digest": mandate.mandate_digest,
            "delegation": "weekly_no_capital_research_mandate",
        }
    else:
        confirmation = db.scalar(
            select(Task).where(
                Task.task_number == _stage_task_number(campaign, source, "C")
            )
        )
        if confirmation is None:
            campaign.phase = "hypothesis_approval"
            campaign.next_action = "founder_hypothesis_card_approval"
            return _create_stage_task(
                db,
                campaign,
                source,
                suffix="C",
                title=f"Approve hypothesis card: {card['title']}",
                contract=_stage_contract(
                    db, campaign, source, stage="draft", hypothesis_card=card
                ),
                approval_required=True,
            )
        if confirmation.status == "succeeded":
            approved = confirmation.result["summary"]
            approval_receipt = {
                "actor": approved["approved_by"],
                "approved_at": approved["approved_at"],
                "plan_digest": approved["plan_digest"],
            }
        else:
            approval = db.scalar(
                select(TaskApproval).where(TaskApproval.task_id == confirmation.id)
            )
            if approval is None or approval.status != "approved":
                campaign.phase = "hypothesis_approval"
                campaign.next_action = "founder_hypothesis_card_approval"
                return confirmation
            consume_task_approval(db, confirmation, now())
            confirmation.status = "succeeded"
            confirmation.completed_at = now()
            confirmation.result = {
                "summary": {
                    "card_digest": digest_document(card),
                    "approved_by": approval.decided_by,
                    "approved_at": approval.issued_at.isoformat(),
                    "plan_digest": approval.plan_digest,
                }
            }
            append_task_event(
                db,
                confirmation,
                "task_succeeded",
                "Founder approved the immutable hypothesis card.",
                payload=confirmation.result["summary"],
            )
            approval_receipt = {
                "actor": approval.decided_by,
                "approved_at": approval.issued_at.isoformat(),
                "plan_digest": approval.plan_digest,
            }
    qualification_task = db.scalar(
        select(Task).where(
            Task.task_number == _stage_task_number(campaign, source, "Q")
        )
    )
    if qualification_task is None:
        campaign.phase = "strategy_qualification"
        campaign.next_action = "compile_and_independently_review_strategy"
        return _create_stage_task(
            db,
            campaign,
            source,
            suffix="Q",
            title="Compile and qualify the approved Bulletproof strategy",
            contract=_stage_contract(
                db,
                campaign,
                source,
                stage="qualify",
                hypothesis_card=card,
                card_approval=approval_receipt,
            ),
            approval_required=False,
        )
    if qualification_task.status != "succeeded":
        campaign.phase = "strategy_qualification"
        campaign.next_action = "await_vm1_strategy_qualification"
        return qualification_task
    qualification = qualification_task.result.get("summary", {}).get("qualification")
    if (
        not isinstance(qualification, dict)
        or qualification.get("qualified") is not True
        or not isinstance(qualification.get("card"), dict)
        or not isinstance(qualification.get("artifact_bundle"), dict)
    ):
        campaign.status = "needs_attention"
        campaign.phase = "strategy_engineering"
        campaign.next_action = "bounded_strategy_engineering"
        campaign.terminal_reason = {
            "category": "strategy_not_qualified",
            "qualification": qualification,
        }
        return qualification_task
    expected_card = deepcopy(card)
    expected_card.update(
        {
            "status": "confirmed",
            "confirmed_by": approval_receipt["actor"],
            "confirmed_at": approval_receipt["approved_at"],
        }
    )
    for field in ("claim", "entry", "exit"):
        if field in expected_card.get("field_provenance", {}):
            expected_card["field_provenance"][field]["state"] = "confirmed"
    frozen = qualification_task.input_contract
    expected_dataset = {
        key: frozen.get(key)
        for key in (
            "dataset_build_id",
            "dataset_digest",
            "venue",
            "instrument",
            "timeframe",
        )
    }
    expected_window = {
        "start": frozen.get("window_start"),
        "end": frozen.get("window_end"),
    }
    if (
        qualification["card"] != expected_card
        or qualification.get("card_digest") != digest_document(expected_card)
        or expected_card.get("research_question")
        != " ".join(source["question"].split())
        or expected_card.get("dataset_binding") != expected_dataset
        or expected_card.get("execution_window") != expected_window
        or qualification.get("dataset") != expected_dataset
        or qualification.get("window") != expected_window
        or qualification.get("parameter_grid") != expected_card.get("parameters")
    ):
        campaign.status = "needs_attention"
        campaign.phase = "strategy_qualification"
        campaign.next_action = "repair_qualification_approval_binding"
        campaign.terminal_reason = {
            "category": "qualification_differs_from_approved_card"
        }
        return qualification_task
    producers = [draft.assigned_agent_id, qualification_task.assigned_agent_id]
    identities = [
        task_producer_identity(db, task) for task in (draft, qualification_task)
    ]
    if any(actor is None for actor in producers) or any(
        identity is None for identity in identities
    ):
        campaign.phase = "independent_strategy_review"
        campaign.next_action = "repair_strategy_producer_provenance"
        campaign.terminal_reason = {"category": "strategy_producer_identity_missing"}
        return qualification_task
    subject = {
        "campaign_digest": campaign.campaign_digest,
        "question_digest": digest_document(
            {"question": " ".join(source["question"].split())}
        ),
        "source_commit": campaign.specification["bulletproof_source_commit"],
        "qualification_task_id": str(qualification_task.id),
        "card_digest": digest_document(qualification["card"]),
        "artifact_bundle_digest": digest_document(qualification["artifact_bundle"]),
        "producer_agent_ids": sorted({str(actor) for actor in producers}),
        "producer_identities": identities,
        "qualifier_identity": identities[1],
    }
    subject_digest = digest_document(subject)
    review_route = db.scalar(
        select(EvaluationRoute)
        .where(
            EvaluationRoute.subject_type == "alpha_strategy_qualification",
            EvaluationRoute.subject_id == str(qualification_task.id),
            EvaluationRoute.subject_digest == subject_digest,
        )
        .order_by(EvaluationRoute.created_at.desc())
        .limit(1)
    )
    if review_route is None:
        routed_producers = [
            ProducerIdentity(actor=identity["agent_id"], **identity)
            for identity in identities
        ]
        review_route = create_route(
            db,
            EvaluationRouteCreate(
                subject_type="alpha_strategy_qualification",
                subject_id=str(qualification_task.id),
                subject_digest=subject_digest,
                producer=routed_producers[1],
                excluded_producers=routed_producers,
                required_review_kinds=["strategy_spec", "causality_leakage"],
                requested_by="alpha-campaign-director",
            ),
        )
    elif review_route.status == "blocked":
        review_route = retry_blocked_route(db, review_route)
    _materialize_strategy_review_tasks(db, review_route, subject, qualification)
    if not alpha_strategy_reviews_approved(
        db,
        review_route,
        subject_digest=subject_digest,
        producer_agent_id=qualification_task.assigned_agent_id,
        excluded_agent_ids=producers,
        excluded_identities=identities,
        qualifier_identity=identities[1],
    ):
        campaign.phase = "independent_strategy_review"
        campaign.next_action = "route_independent_strategy_review"
        campaign.terminal_reason = {
            "category": "independent_strategy_review_pending",
            "subject": subject,
            "subject_digest": subject_digest,
            "route_id": str(review_route.id) if review_route else None,
            "route_status": review_route.status,
            "routing_blockers": review_route.blocked_reason,
        }
        return qualification_task
    independence = require_independence(db, review_route)
    qualification = deepcopy(qualification)
    qualification["governed_review"] = {
        "route_id": str(review_route.id),
        "receipt_digest": independence.receipt_digest,
        "assertion": independence.assertion,
        "subject": subject,
        "verdict": independence.verdict,
    }
    campaign.terminal_reason = {}
    execution = db.scalar(
        select(Task).where(
            Task.task_number == _stage_task_number(campaign, source, "E")
        )
    )
    if execution is None:
        campaign.phase = "execution" if delegated else "execution_approval"
        campaign.next_action = (
            "await_native_bulletproof_execution"
            if delegated
            else "founder_execution_approval"
        )
        return _create_stage_task(
            db,
            campaign,
            source,
            suffix="E",
            title=f"Approve bounded Tier2B execution: {card['title']}",
            contract=_stage_contract(
                db,
                campaign,
                source,
                stage="execute",
                hypothesis_card=qualification["card"],
                qualification=qualification,
            ),
            approval_required=not delegated,
        )
    campaign.phase = (
        "execution" if execution.status != "pending_approval" else "execution_approval"
    )
    campaign.next_action = (
        "founder_execution_approval"
        if execution.status == "pending_approval"
        else "await_native_bulletproof_execution"
    )
    return execution


def _dataset_path(db: Session, campaign: AlphaCampaign, binding: dict) -> str:
    build = db.get(ResearchDatasetBuild, binding["dataset_build_id"])
    manifest = db.get(ResearchDatasetManifest, build.manifest_id) if build else None
    if manifest is None:
        raise HTTPException(409, "Admitted campaign dataset manifest is unavailable.")
    uris = [
        str(item.get("uri", ""))
        for item in manifest.manifest.get("source_objects", [])
        if str(item.get("uri", "")).startswith("file://")
    ]
    if len(uris) != 1:
        raise HTTPException(
            409, "Alpha execution requires exactly one immutable local panel URI."
        )
    path = Path(uris[0].removeprefix("file://")).resolve(strict=False)
    allowed_root = Path("/home/omenka/Projects/bulletproof_bt/research_data").resolve(
        strict=False
    )
    if not path.is_relative_to(allowed_root) or path.suffix != ".parquet":
        raise HTTPException(409, "Admitted panel path is outside the read-only lake.")
    return str(path)


def _ensure_execution_task(db: Session, campaign: AlphaCampaign) -> Task | None:
    if campaign.status != "running":
        return None
    if campaign.specification.get("execution_protocol") in {
        "alpha003-governed-v1",
        "alpha004-delegated-v1",
    }:
        return _advance_governed_pipeline(db, campaign)
    if campaign.specification.get("execution_protocol") != "alpha002-native-v1":
        return None
    queue = campaign.specification["research_queue"]
    if campaign.hypothesis_count >= len(queue):
        return None
    source = queue[campaign.hypothesis_count]
    task_number = _execution_task_number(campaign, source)
    existing = db.scalar(select(Task).where(Task.task_number == task_number))
    if existing is not None:
        return existing
    binding = campaign.specification["dataset_bindings"][0]
    question = " ".join(source["question"].split())
    from app.schemas.retrieval import HybridRetrievalRequest
    from app.services.evidence import ORCHESTRATOR_ACCESS
    from app.services.retrieval import hybrid_search

    try:
        retrieval = hybrid_search(
            db,
            HybridRetrievalRequest(query=question, limit=5),
            ORCHESTRATOR_ACCESS,
        )
        citations = [
            {
                "object_id": str(hit["object_id"]),
                "content_digest": hit["citation"]["content_digest"],
                "coordinates": hit["citation"]["coordinates"],
                "text": hit["text"][:1200],
                "confidence": hit["confidence"],
            }
            for hit in retrieval["hits"]
        ]
        corpus_digest = retrieval["corpus_digest"]
        retrieval_abstained = retrieval["abstained"]
    except HTTPException as exc:
        citations = []
        corpus_digest = None
        retrieval_abstained = True
        retrieval_error = str(exc.detail)
    task = build_task(
        TaskCreate(
            task_number=task_number,
            project="bulletproof_bt",
            task_type="alpha_research_execution",
            title=f"ALPHA-002 question {source['rank']}: {question[:180]}",
            objective=(
                "Produce a reproducible, no-capital answer using the exact admitted "
                "dataset and Bulletproof classic engine, or retain a bounded "
                "strategy-engineering requirement without substituting a proxy."
            ),
            priority=85,
            risk_level=0,
            created_by="alpha-campaign-director",
            input_contract={
                "repository": "bulletproof_bt",
                "workflow": "alpha-research-execution",
                "base_ref": campaign.specification["bulletproof_source_commit"],
                "campaign_id": str(campaign.id),
                "campaign_digest": campaign.campaign_digest,
                "source_candidate_id": source["source_candidate_id"],
                "source_candidate_digest": source["source_candidate_digest"],
                "question": question,
                "question_digest": digest_document({"question": question}),
                "domain_key": source["domain_key"],
                "dataset_build_id": binding["dataset_build_id"],
                "dataset_digest": binding["dataset_digest"],
                "dataset_path": _dataset_path(db, campaign, binding),
                "memory_database": (
                    "/home/omenka/.local/state/invariance-swarm/alpha002-memory.sqlite"
                ),
                "bundle_root": (
                    "/home/omenka/.local/share/invariance-swarm/alpha002-bundles"
                ),
                "dataset_key": binding["dataset_key"],
                "instrument": campaign.specification["allowed_instruments"][0],
                "timeframe": "1m",
                "tier": "Tier2B",
                "max_variants": campaign.budget["max_variants_per_hypothesis"],
                "research_context": {
                    "corpus_digest": corpus_digest,
                    "abstained": retrieval_abstained,
                    "citations": citations,
                    **(
                        {"error": retrieval_error}
                        if "retrieval_error" in locals()
                        else {}
                    ),
                },
                "authority": "no_capital",
            },
            expected_outputs=[
                "cited hypothesis card or bounded engineering requirement",
                "classic-engine truth receipt when executable",
                "digest-finalized evidence bundle",
            ],
            acceptance_criteria=[
                "exact question and immutable dataset bindings are preserved",
                "unsupported questions are not mapped to similar strategies",
                "no capital, order, promotion or self-approval authority exists",
            ],
            approval_policy={
                "kind": "registry_gate",
                "risk": 0,
                "campaign_activation_digest": campaign.campaign_digest,
            },
            approval_required=False,
            required_capabilities=[
                "alpha-research-execution",
                "backtesting",
                "research-audit",
            ],
            allowed_machines=["vm1-developer"],
            max_attempts=3,
        )
    )
    persist_new_task(db, task)
    db.add(
        FounderNotification(
            kind="alpha_campaign_update",
            entity_id=task.id,
            deduplication_key=f"alpha-task-ready:{task.id}:{task.plan_digest}",
            state="pending",
            payload={
                "campaign_id": str(campaign.id),
                "task_id": str(task.id),
                "state": "queued",
                "phase": "await_vm1_executor",
                "summary": question[:500],
            },
        )
    )
    _append_event(
        db,
        campaign,
        "execution_task_created",
        "alpha-campaign-director",
        {
            "task_id": str(task.id),
            "task_number": task.task_number,
            "source_candidate_id": source["source_candidate_id"],
            "question_digest": task.input_contract["question_digest"],
        },
    )
    return task


def _publication_envelope_from_result(result: dict) -> dict | None:
    summary = result.get("summary", {})
    handoff = result.get("downstream_handoff", {})
    publication_envelope = (
        handoff.get("publication_envelope") if isinstance(handoff, dict) else None
    )
    if publication_envelope is None and isinstance(summary, dict):
        publication_envelope = summary.get("publication_envelope")
    return publication_envelope if isinstance(publication_envelope, dict) else None


def _consume_execution_task(db: Session, campaign: AlphaCampaign) -> bool:
    queue = campaign.specification["research_queue"]
    if campaign.hypothesis_count >= len(queue):
        return False
    source = queue[campaign.hypothesis_count]
    number = (
        _stage_task_number(campaign, source, "E")
        if campaign.specification.get("execution_protocol")
        in {"alpha003-governed-v1", "alpha004-delegated-v1"}
        else _execution_task_number(campaign, source)
    )
    task = db.scalar(select(Task).where(Task.task_number == number))
    if task is None or task.status != "succeeded":
        return False
    summary = task.result.get("summary", {})
    raw_attempt = summary.get("alpha_campaign_attempt")
    if not isinstance(raw_attempt, dict):
        raise HTTPException(
            409, "Completed alpha task lacks a campaign attempt receipt."
        )
    publication_envelope = _publication_envelope_from_result(task.result)
    if publication_envelope is not None:
        from app.services.alpha_publication import publish_execution

        publication = publish_execution(db, publication_envelope)
        raw_attempt = {
            **raw_attempt,
            "governed_bridge_id": publication["bridge_id"],
            "outcome": publication["outcome"],
            "failure_stage": None,
            "gate_report": publication["gate_report"],
            "evidence_digests": publication["evidence_digests"],
        }
    payload = AlphaCampaignAttemptCreate.model_validate(raw_attempt)
    record_attempt(db, campaign, payload)
    _append_event(
        db,
        campaign,
        "execution_task_consumed",
        "alpha-campaign-director",
        {"task_id": str(task.id), "attempt_key": payload.attempt_key},
    )
    db.add(
        FounderNotification(
            kind="alpha_campaign_update",
            entity_id=campaign.id,
            deduplication_key=(
                f"alpha-attempt:{campaign.id}:{payload.attempt_key}:"
                f"{payload.evidence_digests[0]}"
            ),
            state="pending",
            payload={
                "campaign_id": str(campaign.id),
                "task_id": str(task.id),
                "state": payload.outcome,
                "phase": payload.failure_stage or "terminal_evidence",
                "summary": payload.question[:500],
            },
        )
    )
    return True


def _bound_dataset(campaign: AlphaCampaign, build_id, digest: str) -> bool:
    return any(
        item["dataset_build_id"] == str(build_id) and item["dataset_digest"] == digest
        for item in campaign.specification["dataset_bindings"]
    )


def record_attempt(
    db: Session, campaign: AlphaCampaign, payload: AlphaCampaignAttemptCreate
) -> AlphaCampaignAttempt:
    if campaign.status != "running":
        raise HTTPException(409, "Attempts are accepted only for running campaigns.")
    if campaign.campaign_digest != payload.expected_campaign_digest:
        raise HTTPException(409, "Campaign digest changed before attempt publication.")
    if payload.source_commit != campaign.specification["bulletproof_source_commit"]:
        raise HTTPException(
            422, "Bulletproof source commit is outside the frozen campaign."
        )
    if not _bound_dataset(campaign, payload.dataset_build_id, payload.dataset_digest):
        raise HTTPException(
            422, "Attempt dataset is outside the admitted real-data campaign scope."
        )
    existing = db.scalar(
        select(AlphaCampaignAttempt).where(
            (AlphaCampaignAttempt.campaign_id == campaign.id)
            & (AlphaCampaignAttempt.attempt_key == payload.attempt_key)
        )
    )
    if existing is not None:
        existing_document = {
            key: value
            for key, value in payload.model_dump(
                mode="json", exclude={"expected_campaign_digest"}
            ).items()
        }
        stored_document = {key: getattr(existing, key) for key in existing_document}
        stored_document = AlphaCampaignAttemptCreate.model_validate(
            {**stored_document, "expected_campaign_digest": campaign.campaign_digest}
        ).model_dump(mode="json", exclude={"expected_campaign_digest"})
        if existing_document != stored_document:
            raise HTTPException(
                409, "Attempt key is already bound to different evidence."
            )
        return existing
    if payload.trial_count > campaign.budget["max_variants_per_hypothesis"]:
        raise HTTPException(422, "Attempt exceeds its frozen variant budget.")
    if campaign.hypothesis_count + 1 > campaign.budget["max_hypotheses"]:
        raise HTTPException(409, "Campaign hypothesis budget is exhausted.")
    if campaign.trial_count + payload.trial_count > campaign.budget["max_total_trials"]:
        raise HTTPException(409, "Campaign trial budget is exhausted.")
    actual_question_digest = digest_document(
        {"question": " ".join(payload.question.split())}
    )
    if actual_question_digest != payload.question_digest:
        raise HTTPException(409, "Question digest does not match normalized content.")
    source = next(
        (
            item
            for item in campaign.specification["research_queue"]
            if item["source_candidate_id"] == str(payload.source_candidate_id)
        ),
        None,
    )
    if (
        source is None
        or source["source_candidate_digest"] != payload.source_candidate_digest
        or " ".join(source["question"].split()) != " ".join(payload.question.split())
    ):
        raise HTTPException(
            422, "Attempt is not bound to a selected immutable discovery question."
        )
    prior_source_attempt = db.scalar(
        select(AlphaCampaignAttempt).where(
            (AlphaCampaignAttempt.campaign_id == campaign.id)
            & (AlphaCampaignAttempt.source_candidate_id == payload.source_candidate_id)
        )
    )
    if prior_source_attempt is not None:
        raise HTTPException(
            409, "Selected discovery question already has a retained campaign answer."
        )
    bridge = (
        db.get(GovernedResearchBridge, payload.governed_bridge_id)
        if payload.governed_bridge_id
        else None
    )
    if payload.outcome == "candidate":
        if bridge is None or bridge.state != "complete":
            raise HTTPException(
                422,
                "Candidate publication requires a complete governed Bulletproof bridge.",
            )
        dataset_document = bridge.proposal.get("dataset", {})
        bridge_dataset = next(
            (
                dataset_document.get(key)
                for key in ("dataset_digest", "content_digest", "digest")
                if dataset_document.get(key)
            ),
            None,
        )
        if bridge_dataset != payload.dataset_digest:
            raise HTTPException(
                422, "Candidate bridge is not bound to the admitted dataset digest."
            )
        if (
            "independently_reviewed" not in bridge.receipts
            or "published" not in bridge.receipts
        ):
            raise HTTPException(
                422,
                "Candidate bridge lacks independent-review or publication receipts.",
            )
    document = payload.model_dump(
        mode="json", exclude={"expected_campaign_digest", "attempt_key"}
    )
    ordinal = campaign.hypothesis_count + 1
    attempt_digest = digest_document(
        {
            "campaign_digest": campaign.campaign_digest,
            "ordinal": ordinal,
            "attempt_key": payload.attempt_key,
            "attempt": document,
        }
    )
    attempt = AlphaCampaignAttempt(
        campaign_id=campaign.id,
        ordinal=ordinal,
        attempt_key=payload.attempt_key,
        attempt_digest=attempt_digest,
        **document,
    )
    db.add(attempt)
    db.flush()
    campaign.hypothesis_count += 1
    campaign.trial_count += payload.trial_count
    campaign.heartbeat_at = now()
    if payload.outcome == "candidate":
        campaign.status = "shadow_candidate"
        campaign.phase = "complete"
        campaign.next_action = "founder_shadow_review"
        campaign.candidate_attempt_id = attempt.id
        campaign.completed_at = campaign.heartbeat_at
        campaign.consecutive_failures = 0
    else:
        campaign.consecutive_failures = (
            campaign.consecutive_failures + 1 if payload.outcome == "failed" else 0
        )
        campaign.phase = "hypothesis"
        campaign.next_action = "compile_evidence_grounded_hypothesis"
    _append_event(
        db,
        campaign,
        "attempt_retained",
        "alpha-research-runner",
        {
            "attempt_id": str(attempt.id),
            "attempt_digest": attempt.attempt_digest,
            "outcome": attempt.outcome,
            "evidence_digests": attempt.evidence_digests,
        },
    )
    reconcile_campaign(db, campaign)
    return attempt


def reconcile_campaign(db: Session, campaign: AlphaCampaign) -> None:
    campaign.heartbeat_at = now()
    if campaign.status != "running":
        return
    if _consume_execution_task(db, campaign):
        return
    deadline = campaign.activated_at + timedelta(
        seconds=campaign.budget["max_duration_seconds"]
    )
    reason = None
    if campaign.heartbeat_at >= deadline:
        reason = {"category": "duration_budget_exhausted"}
    elif campaign.consecutive_failures >= campaign.budget["max_consecutive_failures"]:
        campaign.status = "needs_attention"
        campaign.phase = "complete"
        campaign.next_action = "operator_review"
        campaign.completed_at = campaign.heartbeat_at
        campaign.terminal_reason = {"category": "consecutive_failure_limit"}
        _append_event(
            db,
            campaign,
            "campaign_needs_attention",
            "alpha-campaign-director",
            campaign.terminal_reason,
        )
        return
    elif campaign.hypothesis_count >= len(campaign.specification["research_queue"]):
        reason = {"category": "selected_research_queue_exhausted"}
    elif campaign.hypothesis_count >= campaign.budget["max_hypotheses"]:
        reason = {"category": "hypothesis_budget_exhausted"}
    elif campaign.trial_count >= campaign.budget["max_total_trials"]:
        reason = {"category": "trial_budget_exhausted"}
    if reason:
        campaign.status = "completed_no_candidate"
        campaign.phase = "complete"
        campaign.next_action = "founder_closeout_review"
        campaign.completed_at = campaign.heartbeat_at
        campaign.terminal_reason = reason
        _append_event(
            db,
            campaign,
            "campaign_completed_no_candidate",
            "alpha-campaign-director",
            reason,
        )
        return
    if campaign.specification.get("execution_protocol") in {
        "alpha003-governed-v1",
        "alpha004-delegated-v1",
    }:
        task = _advance_governed_pipeline(db, campaign)
        if task is not None and task.status in {"failed", "cancelled"}:
            campaign.status = "needs_attention"
            campaign.phase = "complete"
            campaign.next_action = "operator_review"
            campaign.completed_at = campaign.heartbeat_at
            campaign.terminal_reason = {
                "category": f"governed_pipeline_task_{task.status}",
                "task_id": str(task.id),
                "task_number": task.task_number,
                "failure": task.failure,
            }
            _append_event(
                db,
                campaign,
                "campaign_needs_attention",
                "alpha-campaign-director",
                campaign.terminal_reason,
            )
        return
    task = _ensure_execution_task(db, campaign)
    if task is not None:
        if task.status in {"failed", "cancelled"}:
            campaign.status = "needs_attention"
            campaign.phase = "complete"
            campaign.next_action = "operator_review"
            campaign.completed_at = campaign.heartbeat_at
            campaign.terminal_reason = {
                "category": f"execution_task_{task.status}",
                "task_id": str(task.id),
                "task_number": task.task_number,
                "failure": task.failure,
            }
            _append_event(
                db,
                campaign,
                "campaign_needs_attention",
                "alpha-campaign-director",
                campaign.terminal_reason,
            )
            return
        campaign.phase = "execution"
        campaign.next_action = {
            "queued": "await_vm1_executor",
            "leased": "executor_lease_acquired",
            "running": "native_bulletproof_execution",
            "failed": "operator_review_failed_execution",
            "cancelled": "operator_review_cancelled_execution",
        }.get(task.status, "await_executor_terminal_receipt")


def resume_campaign(
    db: Session, campaign: AlphaCampaign, payload: AlphaCampaignAction
) -> None:
    if campaign.status != "needs_attention":
        raise HTTPException(409, "Only a campaign needing attention can be resumed.")
    if campaign.campaign_digest != payload.expected_campaign_digest:
        raise HTTPException(409, "Campaign digest changed before recovery.")
    terminal = campaign.terminal_reason or {}
    if not str(terminal.get("category", "")).startswith("governed_pipeline_task_"):
        raise HTTPException(
            409, "Campaign recovery is limited to governed pipeline task failures."
        )
    failed_task_id = terminal.get("task_id")
    try:
        task_id = UUID(str(failed_task_id))
    except (TypeError, ValueError):
        task_id = None
    task = db.get(Task, task_id) if task_id else None
    if task is None:
        raise HTTPException(409, "Recorded pipeline task is unavailable.")
    if task.status in {"failed", "cancelled"}:
        raise HTTPException(
            409, "Resume the recorded pipeline task before resuming its campaign."
        )

    prior_reason = campaign.terminal_reason
    campaign.status = "running"
    campaign.phase = "recovery"
    campaign.next_action = "reconcile_recovered_pipeline_task"
    campaign.completed_at = None
    campaign.terminal_reason = {}
    campaign.heartbeat_at = now()
    _append_event(
        db,
        campaign,
        "campaign_resumed",
        payload.actor,
        {
            "reason": payload.reason,
            "recovered_task_id": str(task.id),
            "recovered_task_status": task.status,
            "prior_terminal_reason": prior_reason,
        },
    )
    reconcile_campaign(db, campaign)


def cancel_campaign(
    db: Session, campaign: AlphaCampaign, payload: AlphaCampaignAction
) -> None:
    if campaign.status in TERMINAL and campaign.status != "needs_attention":
        raise HTTPException(409, "Terminal campaigns cannot be cancelled again.")
    if campaign.campaign_digest != payload.expected_campaign_digest:
        raise HTTPException(409, "Campaign digest changed before cancellation.")
    campaign.status = "cancelled"
    campaign.phase = "complete"
    campaign.next_action = "none"
    campaign.completed_at = campaign.heartbeat_at = now()
    campaign.terminal_reason = {
        "category": "operator_cancelled",
        "reason": payload.reason,
    }
    task = db.scalar(
        select(Task)
        .where(Task.task_number.like(f"A%-{str(campaign.id)[:8]}-%"))
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    if task is not None and task.status not in {"succeeded", "failed", "cancelled"}:
        stamp = now()
        task.cancel_requested_at = stamp
        task.cancel_reason = payload.reason
        if task.status not in {"leased", "running"}:
            from app.services.agent_context import discard_working_memory
            from app.services.tasks import append_task_event, clear_lease

            task.status = "cancelled"
            task.completed_at = stamp
            clear_lease(task)
            discard_working_memory(db, task.id)
            cooperative = False
            event_type = "task_cancelled"
        else:
            from app.services.tasks import append_task_event

            cooperative = True
            event_type = "task_cancellation_requested"
        append_task_event(
            db,
            task,
            event_type,
            "ALPHA-002 campaign cancellation propagated to its executor.",
            payload={"cooperative": cooperative, "campaign_id": str(campaign.id)},
        )
    _append_event(
        db, campaign, "campaign_cancelled", payload.actor, campaign.terminal_reason
    )


def serialize_campaign(db: Session, campaign: AlphaCampaign) -> dict:
    attempts = db.scalars(
        select(AlphaCampaignAttempt)
        .where(AlphaCampaignAttempt.campaign_id == campaign.id)
        .order_by(AlphaCampaignAttempt.ordinal)
    ).all()
    events = db.scalars(
        select(AlphaCampaignEvent)
        .where(AlphaCampaignEvent.campaign_id == campaign.id)
        .order_by(AlphaCampaignEvent.sequence)
    ).all()
    execution_task = db.scalar(
        select(Task)
        .where(Task.task_number.like(f"A%-{str(campaign.id)[:8]}-%"))
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    return {
        "id": campaign.id,
        "campaign_key": campaign.campaign_key,
        "version": campaign.version,
        "project": campaign.project,
        "objective": campaign.objective,
        "discovery_portfolio_id": campaign.discovery_portfolio_id,
        "campaign_digest": campaign.campaign_digest,
        "specification": campaign.specification,
        "budget": campaign.budget,
        "status": campaign.status,
        "phase": campaign.phase,
        "next_action": campaign.next_action,
        "hypothesis_count": campaign.hypothesis_count,
        "trial_count": campaign.trial_count,
        "consecutive_failures": campaign.consecutive_failures,
        "terminal_reason": campaign.terminal_reason,
        "candidate_attempt_id": campaign.candidate_attempt_id,
        "created_by": campaign.created_by,
        "created_at": campaign.created_at,
        "activated_at": campaign.activated_at,
        "heartbeat_at": campaign.heartbeat_at,
        "completed_at": campaign.completed_at,
        "attempts": [
            {
                "id": item.id,
                "ordinal": item.ordinal,
                "attempt_key": item.attempt_key,
                "attempt_digest": item.attempt_digest,
                "question": item.question,
                "question_digest": item.question_digest,
                "source_candidate_id": item.source_candidate_id,
                "source_candidate_digest": item.source_candidate_digest,
                "hypothesis_id": item.hypothesis_id,
                "hypothesis_digest": item.hypothesis_digest,
                "dataset_build_id": item.dataset_build_id,
                "dataset_digest": item.dataset_digest,
                "governed_bridge_id": item.governed_bridge_id,
                "trial_count": item.trial_count,
                "outcome": item.outcome,
                "failure_stage": item.failure_stage,
                "gate_report": item.gate_report,
                "evidence_digests": item.evidence_digests,
                "produced_by": item.produced_by,
                "source_commit": item.source_commit,
                "created_at": item.created_at,
            }
            for item in attempts
        ],
        "events": [
            {
                "sequence": item.sequence,
                "event_type": item.event_type,
                "actor": item.actor,
                "payload": item.payload,
                "previous_digest": item.previous_digest,
                "event_digest": item.event_digest,
                "created_at": item.created_at,
            }
            for item in events
        ],
        "execution": (
            {
                "task_id": str(execution_task.id),
                "task_number": execution_task.task_number,
                "status": execution_task.status,
                "attempt_count": execution_task.attempt_count,
                "max_attempts": execution_task.max_attempts,
                "heartbeat_at": execution_task.last_execution_heartbeat_at,
                "failure": execution_task.failure,
                "disposition": execution_task.result.get("summary", {}).get(
                    "disposition"
                ),
            }
            if execution_task is not None
            else None
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
