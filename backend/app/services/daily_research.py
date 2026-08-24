from __future__ import annotations

import hashlib
import json
import re
import statistics
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ResearchDailyCycle,
    ResearchDailyCycleEvent,
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchProgram,
    ResearchResult,
    ResearchReview,
    ResearchTrial,
    Task,
)
from app.models.surveillance import SurveillancePublication, SurveillanceRoutingEvent
from app.schemas.research_program import (
    ResearchCycleApproval,
    ResearchCycleLink,
    ResearchProgramCreate,
)


def question_digest(question: str) -> str:
    normalized = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    return hashlib.sha256(normalized.encode()).hexdigest()


def _record_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def rank_daily_candidates(
    candidates: list[dict],
    prior_questions: list[str],
    *,
    now: datetime,
    max_age_days: int = 30,
) -> list[dict]:
    prior_tokens = [_tokens(item) for item in prior_questions]
    ranked: list[dict] = []
    for candidate in candidates:
        if candidate["publication_status"] == "retracted":
            continue
        age_days = max(0.0, (now - candidate["created_at"]).total_seconds() / 86400)
        if age_days > max_age_days:
            continue
        tokens = _tokens(candidate["question"])
        duplicate_score = max(
            (
                len(tokens & prior) / len(tokens | prior)
                for prior in prior_tokens
                if tokens | prior
            ),
            default=0.0,
        )
        if duplicate_score >= 0.8:
            continue
        freshness = max(0.0, 1.0 - age_days / max_age_days)
        score = (
            0.40 * float(candidate["priority_score"])
            + 0.25 * float(candidate["novelty_score"])
            + 0.20 * float(candidate["evidence_quality"])
            + 0.10 * freshness
            + 0.05 * (1.0 - duplicate_score)
        )
        ranked.append(
            candidate
            | {
                "duplicate_score": round(duplicate_score, 6),
                "freshness_score": round(freshness, 6),
                "director_score": round(score, 6),
            }
        )
    return sorted(
        ranked,
        key=lambda item: (-item["director_score"], question_digest(item["question"])),
    )


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def create_program(db: Session, payload: ResearchProgramCreate) -> ResearchProgram:
    record = ResearchProgram(
        program_key=payload.program_key,
        title=payload.title,
        mandate=[item.model_dump(mode="json") for item in payload.mandate],
        schedule=payload.schedule.model_dump(mode="json"),
        budget=payload.budget.model_dump(mode="json"),
        active=payload.active,
        created_by=payload.created_by,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Research program key exists."
        ) from exc
    db.refresh(record)
    return record


def reconcile_programs(
    db: Session, *, now: datetime | None = None
) -> list[ResearchDailyCycle]:
    now = now or datetime.now(UTC)
    programs = db.scalars(
        select(ResearchProgram)
        .where(ResearchProgram.active.is_(True))
        .order_by(ResearchProgram.created_at)
        .with_for_update(skip_locked=True)
    ).all()
    created: list[ResearchDailyCycle] = []
    for program in programs:
        schedule = program.schedule
        if (
            now.weekday() not in schedule["weekdays_utc"]
            or now.hour < schedule["hour_utc"]
        ):
            continue
        existing = db.scalar(
            select(ResearchDailyCycle).where(
                ResearchDailyCycle.program_id == program.id,
                ResearchDailyCycle.cycle_date == now.date(),
            )
        )
        if existing is not None:
            if (
                existing.status == "awaiting_brief"
                and existing.digest.get("selection", {}).get("schema_version")
                != "daily-research-selection-v1.0.0"
            ):
                selection = {
                    "schema_version": "daily-research-selection-v1.0.0",
                    "mode": "static_fallback",
                    "reason": "legacy_cycle_adopted_after_director_deployment",
                    "candidate_count": 0,
                }
                existing.digest = existing.digest | {"selection": selection}
                _event(
                    db,
                    existing,
                    1,
                    "proposal_created",
                    {
                        "question_digest": existing.question_digest,
                        "selection": selection,
                        "approval_required": True,
                        "execution_authority": False,
                    },
                )
                db.flush()
                created.append(existing)
            refresh_cycle(db, existing, now=now)
            continue
        week_start = now.date() - timedelta(days=now.weekday())
        weekly_count = (
            db.scalar(
                select(func.count(ResearchDailyCycle.id)).where(
                    ResearchDailyCycle.program_id == program.id,
                    ResearchDailyCycle.cycle_date >= week_start,
                )
            )
            or 0
        )
        if weekly_count >= int(program.budget["max_cycles_per_week"]):
            continue
        total_count = (
            db.scalar(
                select(func.count(ResearchDailyCycle.id)).where(
                    ResearchDailyCycle.program_id == program.id
                )
            )
            or 0
        )
        prior_hypotheses = list(db.scalars(select(ResearchHypothesis)).all())
        candidate_rows = list(
            db.execute(
                select(SurveillancePublication, SurveillanceRoutingEvent)
                .join(
                    SurveillanceRoutingEvent,
                    SurveillanceRoutingEvent.publication_id
                    == SurveillancePublication.id,
                )
                .where(SurveillanceRoutingEvent.decision == "propose_question")
                .where(SurveillanceRoutingEvent.decided_by == "founder-operator")
                .order_by(SurveillanceRoutingEvent.created_at.desc())
            ).all()
        )
        prior_cycles = db.execute(
            select(
                ResearchDailyCycle.id,
                ResearchDailyCycle.question,
                ResearchDailyCycle.digest,
            ).where(ResearchDailyCycle.program_id == program.id)
        ).all()
        prior_questions = [
            item.specification["research_question"] for item in prior_hypotheses
        ] + [cycle_question for _, cycle_question, _ in prior_cycles]
        used_publication_ids = {
            str((cycle_digest or {})["selection"]["publication_id"])
            for _, _, cycle_digest in prior_cycles
            if (cycle_digest or {}).get("selection", {}).get("publication_id")
        }
        candidates = []
        considered_publication_ids: set[str] = set()
        for publication, event in candidate_rows:
            publication_id = str(publication.id)
            if (
                publication_id in used_publication_ids
                or publication_id in considered_publication_ids
            ):
                continue
            considered_publication_ids.add(publication_id)
            candidates.append(
                {
                    "publication_id": publication_id,
                    "content_digest": publication.content_digest,
                    "question": event.proposal["proposed_question"],
                    "rationale": event.rationale,
                    "source": "approved_research_intelligence",
                    "tags": list(
                        publication.assessment["technique_brief"][
                            "applicability_domains"
                        ]
                    ),
                    "priority_score": publication.routing["priority_score"],
                    "novelty_score": publication.assessment["novelty_score"],
                    "evidence_quality": publication.assessment["evidence_quality"],
                    "publication_status": publication.publication_status,
                    "created_at": publication.created_at,
                    "approval_event_id": str(event.id),
                    "approval_event_digest": event.event_digest,
                    "citation": publication.provenance,
                }
            )
        ranked = rank_daily_candidates(candidates, prior_questions, now=now)
        if ranked:
            selected = ranked[0]
            question = {
                "question_key": f"ri-{selected['content_digest'][:16]}",
                "question": selected["question"],
                "rationale": selected["rationale"],
                "source": selected["source"],
                "tags": selected["tags"],
            }
            selection = {
                "schema_version": "daily-research-selection-v1.0.0",
                "mode": "approved_research_intelligence",
                "publication_id": selected["publication_id"],
                "publication_digest": selected["content_digest"],
                "approval_event_id": selected["approval_event_id"],
                "approval_event_digest": selected["approval_event_digest"],
                "citation": selected["citation"],
                "institutional_gap": {
                    "domains": selected["tags"],
                    "nearest_prior_similarity": round(
                        1.0 - selected["novelty_score"], 6
                    ),
                    "requires_independent_validation": True,
                    "limitations": [
                        "surveillance evidence is not institutional validation",
                        "an approved question remains untested",
                    ],
                },
                "ranking": {
                    "director_score": selected["director_score"],
                    "novelty_score": selected["novelty_score"],
                    "evidence_quality": selected["evidence_quality"],
                    "duplicate_score": selected["duplicate_score"],
                    "freshness_score": selected["freshness_score"],
                    "candidate_count": len(ranked),
                },
            }
        else:
            question = program.mandate[total_count % len(program.mandate)]
            selection = {
                "schema_version": "daily-research-selection-v1.0.0",
                "mode": "static_fallback",
                "reason": "no_approved_current_novel_candidate",
                "candidate_count": len(candidates),
            }
        digest = question_digest(question["question"])
        duplicate = next(
            (
                item
                for item in prior_hypotheses
                if question_digest(item.specification["research_question"]) == digest
            ),
            None,
        )
        status = "duplicate_avoided" if duplicate else "awaiting_brief"
        cycle = ResearchDailyCycle(
            program_id=program.id,
            cycle_date=now.date(),
            question_key=question["question_key"],
            question=question["question"],
            question_digest=digest,
            status=status,
            budget=program.budget,
            duplicate_hypothesis_id=duplicate.id if duplicate else None,
            digest={
                "rationale": question["rationale"],
                "source": question["source"],
                "tags": question["tags"],
                "selection": selection,
            },
            completed_at=now if duplicate else None,
        )
        db.add(cycle)
        db.flush()
        _event(
            db,
            cycle,
            1,
            "proposal_created",
            {
                "question_digest": digest,
                "selection": selection,
                "approval_required": True,
                "execution_authority": False,
            },
        )
        created.append(cycle)
    return created


def link_cycle(
    db: Session, cycle: ResearchDailyCycle, payload: ResearchCycleLink
) -> ResearchDailyCycle:
    if cycle.status != "awaiting_brief":
        raise HTTPException(
            status_code=409, detail="Cycle is not awaiting registration."
        )
    if (
        cycle.digest.get("selection", {}).get("schema_version")
        == "daily-research-selection-v1.0.0"
        and cycle.digest.get("approval", {}).get("decision") != "approved"
    ):
        raise HTTPException(status_code=409, detail="Cycle proposal is not approved.")
    hypothesis = db.get(ResearchHypothesis, payload.hypothesis_id)
    task = db.get(Task, payload.task_id)
    if hypothesis is None or task is None:
        raise HTTPException(status_code=404, detail="Hypothesis or task not found.")
    if (
        question_digest(hypothesis.specification["research_question"])
        != cycle.question_digest
    ):
        raise HTTPException(
            status_code=422, detail="Hypothesis question does not match cycle."
        )
    cycle.hypothesis_id = hypothesis.id
    cycle.task_id = task.id
    cycle.status = "registered"
    refresh_cycle(db, cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def decide_cycle(
    db: Session, cycle: ResearchDailyCycle, payload: ResearchCycleApproval
) -> ResearchDailyCycle:
    if cycle.status != "awaiting_brief":
        raise HTTPException(status_code=409, detail="Cycle is not awaiting approval.")
    if payload.expected_question_digest != cycle.question_digest:
        raise HTTPException(status_code=409, detail="Cycle question digest changed.")
    existing = list(
        db.scalars(
            select(ResearchDailyCycleEvent).where(
                ResearchDailyCycleEvent.cycle_id == cycle.id,
                ResearchDailyCycleEvent.event_type.in_(("approved", "rejected")),
            )
        ).all()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Cycle proposal is already decided."
        )
    detail = {
        "question_digest": cycle.question_digest,
        "decision": payload.decision,
        "rationale": payload.rationale,
        "decided_by": payload.decided_by,
        "execution_authority": False,
    }
    cycle.digest = cycle.digest | {"approval": detail}
    _event(db, cycle, 2, payload.decision, detail)
    if payload.decision == "approved":
        _event(
            db,
            cycle,
            3,
            "task_ready",
            {
                "question_digest": cycle.question_digest,
                "next_action": "compile_hypothesis_brief",
                "approval_required_for_execution": True,
            },
        )
    else:
        cycle.status = "attention_required"
        cycle.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(cycle)
    return cycle


def cycle_events(db: Session, cycle_id) -> list[ResearchDailyCycleEvent]:
    return list(
        db.scalars(
            select(ResearchDailyCycleEvent)
            .where(ResearchDailyCycleEvent.cycle_id == cycle_id)
            .order_by(ResearchDailyCycleEvent.sequence)
        ).all()
    )


def _event(
    db: Session,
    cycle: ResearchDailyCycle,
    sequence: int,
    event_type: str,
    detail: dict,
) -> None:
    document = {
        "cycle_id": str(cycle.id),
        "sequence": sequence,
        "event_type": event_type,
        "detail": detail,
    }
    db.add(
        ResearchDailyCycleEvent(
            cycle_id=cycle.id,
            sequence=sequence,
            event_type=event_type,
            detail=detail,
            record_digest=_record_digest(document),
        )
    )


def refresh_cycle(
    db: Session, cycle: ResearchDailyCycle, *, now: datetime | None = None
) -> ResearchDailyCycle:
    if cycle.task_id is None or cycle.status in {"duplicate_avoided", "completed"}:
        return cycle
    task = db.get(Task, cycle.task_id)
    if task is None:
        cycle.status = "attention_required"
        return cycle
    if task.status in {"leased", "running"}:
        cycle.status = "running"
    elif task.status == "succeeded":
        cycle.status = "completed"
        cycle.completed_at = now or datetime.now(UTC)
    elif task.status in {"failed", "cancelled"}:
        cycle.status = "attention_required"
    else:
        cycle.status = "registered"
    return cycle


def daily_digest(db: Session, day: date) -> dict:
    cycles = db.scalars(
        select(ResearchDailyCycle)
        .where(ResearchDailyCycle.cycle_date == day)
        .order_by(ResearchDailyCycle.created_at)
    ).all()
    for cycle in cycles:
        refresh_cycle(db, cycle)
    learned: list[str] = []
    rejected: list[str] = []
    uncertain: list[str] = []
    for cycle in cycles:
        if cycle.status == "duplicate_avoided":
            learned.append(f"Duplicate avoided: {cycle.question}")
        elif cycle.status == "completed":
            outcome = _cycle_outcome(db, cycle)
            target = rejected if outcome == "rejected" else learned
            target.append(f"{outcome or 'completed'}: {cycle.question}")
        else:
            uncertain.append(f"{cycle.status}: {cycle.question}")
    programs = db.scalars(
        select(ResearchProgram).where(ResearchProgram.active.is_(True))
    ).all()
    next_questions = []
    for program in programs:
        count = (
            db.scalar(
                select(func.count(ResearchDailyCycle.id)).where(
                    ResearchDailyCycle.program_id == program.id
                )
            )
            or 0
        )
        next_questions.append(program.mandate[count % len(program.mandate)]["question"])
    return {
        "date": day,
        "cycles": cycles,
        "learned": learned,
        "rejected": rejected,
        "uncertain": uncertain,
        "next_questions": next_questions,
    }


def weekly_metrics(db: Session, week_start: date) -> dict:
    week_end = week_start + timedelta(days=7)
    cycles = db.scalars(
        select(ResearchDailyCycle).where(
            ResearchDailyCycle.cycle_date >= week_start,
            ResearchDailyCycle.cycle_date < week_end,
        )
    ).all()
    completed = [
        item for item in cycles if refresh_cycle(db, item).status == "completed"
    ]
    outcomes = [_cycle_outcome(db, item) for item in completed]
    negative = sum(item == "rejected" for item in outcomes)
    accepted = sum(item == "accepted" for item in outcomes)
    reproductions: list[bool] = []
    durations: list[float] = []
    for cycle in completed:
        result = _cycle_result(db, cycle)
        if result is None:
            continue
        reviews = db.scalars(
            select(ResearchReview).where(
                ResearchReview.subject_type == "result",
                ResearchReview.subject_id == result.id,
                ResearchReview.review_kind == "independent_review",
            )
        ).all()
        reproductions.extend(
            bool(review.review.get("exact_reproduction")) for review in reviews
        )
        experiment = _cycle_experiment(db, cycle)
        hypothesis = db.get(ResearchHypothesis, cycle.hypothesis_id)
        if experiment is not None and hypothesis is not None:
            durations.append(
                (experiment.registered_at - hypothesis.registered_at).total_seconds()
            )
    trial_count = sum(
        db.scalar(
            select(func.count(ResearchTrial.id))
            .join(ResearchExperiment)
            .where(ResearchExperiment.hypothesis_id == cycle.hypothesis_id)
        )
        or 0
        for cycle in completed
    )
    return {
        "week_start": week_start,
        "cycle_count": len(cycles),
        "completed_count": len(completed),
        "duplicate_work_avoided": sum(
            item.status == "duplicate_avoided" for item in cycles
        ),
        "negative_results_retained": negative,
        "reproduction_rate": sum(reproductions) / len(reproductions)
        if reproductions
        else 0.0,
        "trial_adjusted_survivor_rate": accepted / trial_count if trial_count else 0.0,
        "median_seconds_to_registered_experiment": statistics.median(durations)
        if durations
        else None,
        "terminal_babysitting_events": sum(
            item.status == "attention_required" for item in cycles
        ),
    }


def _cycle_experiment(db: Session, cycle: ResearchDailyCycle):
    if cycle.hypothesis_id is None:
        return None
    return db.scalar(
        select(ResearchExperiment)
        .where(ResearchExperiment.hypothesis_id == cycle.hypothesis_id)
        .order_by(ResearchExperiment.registered_at.desc())
    )


def _cycle_result(db: Session, cycle: ResearchDailyCycle):
    experiment = _cycle_experiment(db, cycle)
    if experiment is None:
        return None
    return db.scalar(
        select(ResearchResult)
        .join(ResearchTrial)
        .where(ResearchTrial.experiment_id == experiment.id)
        .order_by(ResearchResult.recorded_at.desc())
    )


def _cycle_outcome(db: Session, cycle: ResearchDailyCycle) -> str | None:
    result = _cycle_result(db, cycle)
    if result is None:
        return None
    decision = db.scalar(
        select(ResearchDecision)
        .where(ResearchDecision.result_id == result.id)
        .order_by(ResearchDecision.decided_at.desc())
    )
    return result.outcome if decision is not None else None
