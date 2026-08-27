from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.autonomous_research import AutonomousResearchSession
from app.models.curriculum import ResearchBrainEvaluation, ResearchDomainCurriculum
from app.models.discovery import DiscoveryMap
from app.models.discovery_portfolio import (
    DiscoveryPortfolio,
    DiscoveryPortfolioCandidate,
    DiscoveryPortfolioEvent,
)
from app.models.falsification import MechanismEvaluation, MechanismPlan
from app.models.research import ResearchDailyCycle, ResearchProgram
from app.models.selection_audit import SelectionBiasAudit
from app.schemas.discovery_portfolio import DiscoveryPortfolioCreate
from app.services.graph import digest_document, graph_projection_status
from app.services.retrieval import projection_status


def _words(value: str) -> set[str]:
    return {
        word
        for word in "".join(
            character if character.isalnum() else " " for character in value.lower()
        ).split()
        if len(word) > 2
    }


def _similarity(first: str, second: str) -> float:
    left, right = _words(first), _words(second)
    return len(left & right) / len(left | right) if left or right else 1.0


def _curriculum_uncertainty(record: ResearchBrainEvaluation) -> float:
    deficits = []
    for key, threshold in record.thresholds.items():
        if key.startswith("minimum_"):
            metric = record.metrics.get(key.removeprefix("minimum_"), 0.0)
            deficits.append(
                max(0.0, (threshold - metric) / threshold) if threshold else 0.0
            )
        elif key.startswith("maximum_"):
            metric = record.metrics.get(key.removeprefix("maximum_"), 0.0)
            deficits.append(max(0.0, metric - threshold))
    floor = 0.2 if record.passed else 0.6
    return min(1.0, max([floor, *deficits]))


def _source(
    db: Session, payload, project: str, source_epoch: datetime
) -> tuple[float, str]:
    if payload.source_type == "curriculum_evaluation":
        record = db.get(ResearchBrainEvaluation, payload.source_id)
        if record is None or record.record_digest != payload.source_digest:
            raise HTTPException(
                422, "Curriculum evaluation source is absent or digest-mismatched."
            )
        curriculum = db.get(ResearchDomainCurriculum, record.curriculum_id)
        latest = db.scalar(
            select(ResearchBrainEvaluation)
            .where(ResearchBrainEvaluation.curriculum_id == record.curriculum_id)
            .order_by(ResearchBrainEvaluation.evaluated_at.desc())
            .limit(1)
        )
        retrieval, corpus_digest, retrieval_stale = projection_status(db)
        graph, graph_stale = graph_projection_status(db)
        if (
            curriculum is None
            or curriculum.project != project
            or latest is None
            or latest.id != record.id
            or record.evaluated_at > source_epoch
            or retrieval_stale
            or graph_stale
            or record.corpus_digest != corpus_digest
            or record.graph_manifest_digest != graph.manifest_digest
            or retrieval.corpus_digest != corpus_digest
        ):
            raise HTTPException(
                409,
                "Curriculum evaluation source is stale or outside the portfolio project.",
            )
        if payload.domain_key != curriculum.domain_key:
            raise HTTPException(422, "Candidate domain does not match its curriculum.")
        return _curriculum_uncertainty(record), record.record_digest
    if payload.source_type == "discovery_map":
        record = db.get(DiscoveryMap, payload.source_id)
        if record is None or record.map_digest != payload.source_digest:
            raise HTTPException(
                422, "Discovery-map source is absent or digest-mismatched."
            )
        if record.status != "active" or record.registered_at > source_epoch:
            raise HTTPException(
                409, "Discovery-map source is stale, superseded or post-epoch."
            )
        cycle = db.get(ResearchDailyCycle, record.document["source_daily_cycle_id"])
        program = (
            db.get(ResearchProgram, cycle.program_id) if cycle is not None else None
        )
        if program is None or program.project != project:
            raise HTTPException(
                409, "Discovery-map source is outside the portfolio project."
            )
        if " ".join(payload.question.lower().split()) != " ".join(
            record.document["question"].lower().split()
        ):
            raise HTTPException(
                422, "Candidate question does not match its discovery map."
            )
        uncertainty = {
            "observation": 1.0,
            "anomaly": 0.8,
            "mechanism": 0.6,
            "opportunity": 0.35,
        }[record.stage]
        return uncertainty, record.map_digest
    if payload.source_type in {"mechanism_evaluation", "selection_bias_audit"}:
        if payload.source_type == "mechanism_evaluation":
            evaluation = db.get(MechanismEvaluation, payload.source_id)
            record = None
            if (
                evaluation is None
                or evaluation.evaluation_digest != payload.source_digest
                or evaluation.status != "active"
                or evaluation.evaluated_at > source_epoch
            ):
                raise HTTPException(
                    409,
                    "Mechanism evaluation is absent, stale, superseded or post-epoch.",
                )
        else:
            record = db.get(SelectionBiasAudit, payload.source_id)
            if (
                record is None
                or record.audit_digest != payload.source_digest
                or record.status != "active"
                or record.audited_at > source_epoch
            ):
                raise HTTPException(
                    409,
                    "Selection-bias audit is absent, stale, superseded or post-epoch.",
                )
            evaluation = db.get(MechanismEvaluation, record.mechanism_evaluation_id)
        plan = db.get(MechanismPlan, evaluation.plan_id) if evaluation else None
        discovery = db.get(DiscoveryMap, plan.discovery_map_id) if plan else None
        cycle = (
            db.get(ResearchDailyCycle, discovery.document["source_daily_cycle_id"])
            if discovery
            else None
        )
        program = db.get(ResearchProgram, cycle.program_id) if cycle else None
        if (
            evaluation is None
            or evaluation.status != "active"
            or plan is None
            or discovery is None
            or discovery.status != "active"
            or program is None
            or program.project != project
        ):
            raise HTTPException(
                409,
                "Selection-bias audit lineage is stale or outside the portfolio project.",
            )
        expected_question = (
            "What uncertainty remains after mechanism evaluation for: "
            if payload.source_type == "mechanism_evaluation"
            else "How should the selection-bias conclusion alter confidence in: "
        ) + discovery.document["question"]
        if " ".join(payload.question.lower().split()) != " ".join(
            expected_question.lower().split()
        ):
            raise HTTPException(
                422,
                "Candidate question does not match its canonical mechanism lineage.",
            )
        if payload.source_type == "mechanism_evaluation":
            if payload.domain_key != "causal-reasoning":
                raise HTTPException(
                    422, "Mechanism-evaluation candidates require that domain."
                )
            uncertainty = {
                "supported": 0.3,
                "unresolved": 0.8,
                "falsified": 0.2,
            }[evaluation.conclusion]
            return uncertainty, evaluation.evaluation_digest
        if payload.domain_key != "selection-bias":
            raise HTTPException(
                422, "Selection-bias audit candidates require that domain."
            )
        uncertainty = {
            "blocked": 1.0,
            "selection_risk_detected": 0.8,
            "selection_adjusted": 0.4,
        }[record.conclusion]
        return uncertainty, record.audit_digest
    record = db.get(AutonomousResearchSession, payload.source_id)
    if record is None or record.project != project or record.status != "completed":
        raise HTTPException(
            409,
            "Autonomous-session source is absent, incomplete or outside the project.",
        )
    if record.completed_at is None or record.completed_at > source_epoch:
        raise HTTPException(409, "Autonomous-session source is post-epoch.")
    if record.closeout.get("closeout_digest") != payload.source_digest:
        raise HTTPException(422, "Autonomous-session source digest does not match.")
    if " ".join(payload.question.lower().split()) != " ".join(
        record.objective.lower().split()
    ):
        raise HTTPException(
            422, "Candidate question does not match its autonomous session."
        )
    outcomes = set(record.closeout.get("retained_outcomes", []))
    uncertainty = (
        0.7
        if outcomes & {"invalid", "failed"}
        else 0.55
        if "negative" in outcomes
        else 0.25
    )
    return uncertainty, payload.source_digest


def _append_event(db: Session, portfolio: DiscoveryPortfolio, payload: dict):
    event = DiscoveryPortfolioEvent(
        portfolio_id=portfolio.id,
        sequence=1,
        event_type="attention_allocated",
        actor=portfolio.created_by,
        payload=payload,
        previous_digest=None,
        event_digest=digest_document(
            {
                "portfolio_id": str(portfolio.id),
                "sequence": 1,
                "event_type": "attention_allocated",
                "actor": portfolio.created_by,
                "payload": payload,
                "previous_digest": None,
            }
        ),
    )
    db.add(event)
    return event


def register_portfolio(
    db: Session, payload: DiscoveryPortfolioCreate
) -> DiscoveryPortfolio:
    if payload.source_epoch > datetime.now(UTC):
        raise HTTPException(422, "Portfolio source epoch cannot be in the future.")
    prior_questions = [
        item.objective
        for item in db.scalars(
            select(AutonomousResearchSession).where(
                AutonomousResearchSession.project == payload.project,
                AutonomousResearchSession.status == "completed",
                AutonomousResearchSession.completed_at <= payload.source_epoch,
            )
        ).all()
    ]
    verified = []
    for candidate in payload.candidates:
        uncertainty, source_digest = _source(
            db, candidate, payload.project, payload.source_epoch
        )
        competing = [
            item.question
            for item in payload.candidates
            if item.candidate_key != candidate.candidate_key
        ]
        duplicate = max(
            [
                _similarity(candidate.question, question)
                for question in [*competing, *prior_questions]
            ]
            or [0.0]
        )
        novelty = max(0.0, 1.0 - duplicate)
        weighted = (
            payload.policy.relevance_weight * candidate.decision_relevance
            + payload.policy.feasibility_weight * candidate.feasibility
            + payload.policy.novelty_weight * novelty
        )
        gain = uncertainty * weighted / candidate.attention_cost
        document = candidate.model_dump(mode="json") | {
            "source_digest": source_digest,
            "source_uncertainty": round(uncertainty, 8),
            "duplicate_similarity": round(duplicate, 8),
            "novelty": round(novelty, 8),
            "expected_information_gain_per_attention": round(gain, 12),
        }
        document["candidate_digest"] = digest_document(
            {
                "portfolio_key": payload.portfolio_key,
                "version": payload.version,
                "project": payload.project,
                "source_epoch": payload.source_epoch.isoformat(),
                "candidate": document,
            }
        )
        verified.append(document)
    verified.sort(
        key=lambda item: (
            -item["expected_information_gain_per_attention"],
            item["candidate_key"],
        )
    )

    selected: list[dict] = []
    selected_keys: set[str] = set()
    attention = 0
    domain_counts: dict[str, int] = {}
    cluster_counts: dict[str, int] = {}
    best_by_domain = {}
    for item in verified:
        best_by_domain.setdefault(item["domain_key"], item)
    domain_seeds = sorted(
        best_by_domain.values(),
        key=lambda item: (
            -item["expected_information_gain_per_attention"],
            item["candidate_key"],
        ),
    )[: payload.policy.minimum_distinct_domains]

    def can_select(item):
        return (
            len(selected) < payload.policy.maximum_selected
            and attention + item["attention_cost"] <= payload.policy.attention_budget
            and domain_counts.get(item["domain_key"], 0)
            < payload.policy.maximum_per_domain
            and cluster_counts.get(item["cluster_key"], 0)
            < payload.policy.maximum_per_cluster
        )

    def choose(item):
        nonlocal attention
        selected.append(item)
        selected_keys.add(item["candidate_key"])
        attention += item["attention_cost"]
        domain_counts[item["domain_key"]] = domain_counts.get(item["domain_key"], 0) + 1
        cluster_counts[item["cluster_key"]] = (
            cluster_counts.get(item["cluster_key"], 0) + 1
        )

    for item in domain_seeds:
        if not can_select(item):
            raise HTTPException(
                422, "Attention budget cannot satisfy the domain-diversity floor."
            )
        choose(item)
    for item in verified:
        if item["candidate_key"] not in selected_keys and can_select(item):
            choose(item)
    if (
        len({item["domain_key"] for item in selected})
        < payload.policy.minimum_distinct_domains
    ):
        raise HTTPException(422, "Allocation failed the domain-diversity floor.")

    decisions = []
    for item in verified:
        if item["candidate_key"] in selected_keys:
            reason = "selected_by_diversified_information_gain"
            rank = next(
                index + 1
                for index, chosen in enumerate(selected)
                if chosen["candidate_key"] == item["candidate_key"]
            )
        else:
            rank = None
            if (
                domain_counts.get(item["domain_key"], 0)
                >= payload.policy.maximum_per_domain
            ):
                reason = "domain_cap"
            elif (
                cluster_counts.get(item["cluster_key"], 0)
                >= payload.policy.maximum_per_cluster
            ):
                reason = "cluster_cap"
            elif attention + item["attention_cost"] > payload.policy.attention_budget:
                reason = "attention_budget"
            elif len(selected) >= payload.policy.maximum_selected:
                reason = "selection_count_budget"
            else:
                reason = "lower_marginal_information_gain"
        decisions.append(
            item
            | {"selected": rank is not None, "rank": rank, "decision_reason": reason}
        )
    policy = payload.policy.model_dump(mode="json")
    allocation = {
        "portfolio_key": payload.portfolio_key,
        "version": payload.version,
        "project": payload.project,
        "objective": payload.objective,
        "source_epoch": payload.source_epoch.isoformat(),
        "policy": policy,
        "selected": [item["candidate_key"] for item in selected],
        "attention_used": attention,
        "decisions": decisions,
        "action_authority": False,
    }
    portfolio = DiscoveryPortfolio(
        portfolio_key=payload.portfolio_key,
        version=payload.version,
        project=payload.project,
        objective=payload.objective,
        policy=policy,
        policy_digest=digest_document(policy),
        source_epoch=payload.source_epoch,
        status="allocated",
        candidate_count=len(decisions),
        selected_count=len(selected),
        attention_used=attention,
        allocation_digest=digest_document(allocation),
        created_by=payload.created_by,
    )
    db.add(portfolio)
    db.flush()
    for item in decisions:
        db.add(
            DiscoveryPortfolioCandidate(
                portfolio_id=portfolio.id,
                candidate_key=item["candidate_key"],
                domain_key=item["domain_key"],
                cluster_key=item["cluster_key"],
                source_type=item["source_type"],
                source_id=item["source_id"],
                source_digest=item["source_digest"],
                question=item["question"],
                scoring={
                    key: item[key]
                    for key in (
                        "decision_relevance",
                        "feasibility",
                        "attention_cost",
                        "source_uncertainty",
                        "duplicate_similarity",
                        "novelty",
                        "expected_information_gain_per_attention",
                    )
                },
                selected=item["selected"],
                rank=item["rank"],
                decision={"reason": item["decision_reason"]},
                candidate_digest=item["candidate_digest"],
            )
        )
    _append_event(
        db,
        portfolio,
        {
            "allocation_digest": portfolio.allocation_digest,
            "selected": allocation["selected"],
            "attention_used": attention,
        },
    )
    return portfolio


def serialize_portfolio(db: Session, portfolio: DiscoveryPortfolio) -> dict:
    candidates = db.scalars(
        select(DiscoveryPortfolioCandidate)
        .where(DiscoveryPortfolioCandidate.portfolio_id == portfolio.id)
        .order_by(
            DiscoveryPortfolioCandidate.selected.desc(),
            DiscoveryPortfolioCandidate.rank,
            DiscoveryPortfolioCandidate.candidate_key,
        )
    ).all()
    events = db.scalars(
        select(DiscoveryPortfolioEvent)
        .where(DiscoveryPortfolioEvent.portfolio_id == portfolio.id)
        .order_by(DiscoveryPortfolioEvent.sequence)
    ).all()
    return {
        "id": portfolio.id,
        "portfolio_key": portfolio.portfolio_key,
        "version": portfolio.version,
        "project": portfolio.project,
        "objective": portfolio.objective,
        "policy": portfolio.policy,
        "policy_digest": portfolio.policy_digest,
        "source_epoch": portfolio.source_epoch,
        "status": portfolio.status,
        "candidate_count": portfolio.candidate_count,
        "selected_count": portfolio.selected_count,
        "attention_used": portfolio.attention_used,
        "allocation_digest": portfolio.allocation_digest,
        "created_by": portfolio.created_by,
        "created_at": portfolio.created_at,
        "candidates": [
            {
                "candidate_key": item.candidate_key,
                "domain_key": item.domain_key,
                "cluster_key": item.cluster_key,
                "source_type": item.source_type,
                "source_id": str(item.source_id),
                "source_digest": item.source_digest,
                "question": item.question,
                "scoring": item.scoring,
                "selected": item.selected,
                "rank": item.rank,
                "decision": item.decision,
                "candidate_digest": item.candidate_digest,
            }
            for item in candidates
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
    }
