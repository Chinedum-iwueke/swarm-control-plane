from __future__ import annotations

import hashlib
import re
import statistics
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ResearchDailyCycle,
    ResearchDecision,
    ResearchExperiment,
    ResearchHypothesis,
    ResearchProgram,
    ResearchResult,
    ResearchReview,
    ResearchTrial,
    Task,
)
from app.schemas.research_program import ResearchCycleLink, ResearchProgramCreate


def question_digest(question: str) -> str:
    normalized = " ".join(re.findall(r"[a-z0-9]+", question.lower()))
    return hashlib.sha256(normalized.encode()).hexdigest()


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
        raise HTTPException(status_code=409, detail="Research program key exists.") from exc
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
        if now.weekday() not in schedule["weekdays_utc"] or now.hour < schedule["hour_utc"]:
            continue
        existing = db.scalar(
            select(ResearchDailyCycle).where(
                ResearchDailyCycle.program_id == program.id,
                ResearchDailyCycle.cycle_date == now.date(),
            )
        )
        if existing is not None:
            refresh_cycle(db, existing, now=now)
            continue
        week_start = now.date() - timedelta(days=now.weekday())
        weekly_count = db.scalar(
            select(func.count(ResearchDailyCycle.id)).where(
                ResearchDailyCycle.program_id == program.id,
                ResearchDailyCycle.cycle_date >= week_start,
            )
        ) or 0
        if weekly_count >= int(program.budget["max_cycles_per_week"]):
            continue
        total_count = db.scalar(
            select(func.count(ResearchDailyCycle.id)).where(
                ResearchDailyCycle.program_id == program.id
            )
        ) or 0
        question = program.mandate[total_count % len(program.mandate)]
        digest = question_digest(question["question"])
        duplicate = next(
            (
                item
                for item in db.scalars(select(ResearchHypothesis)).all()
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
            },
            completed_at=now if duplicate else None,
        )
        db.add(cycle)
        db.flush()
        created.append(cycle)
    return created


def link_cycle(
    db: Session, cycle: ResearchDailyCycle, payload: ResearchCycleLink
) -> ResearchDailyCycle:
    if cycle.status != "awaiting_brief":
        raise HTTPException(status_code=409, detail="Cycle is not awaiting registration.")
    hypothesis = db.get(ResearchHypothesis, payload.hypothesis_id)
    task = db.get(Task, payload.task_id)
    if hypothesis is None or task is None:
        raise HTTPException(status_code=404, detail="Hypothesis or task not found.")
    if question_digest(hypothesis.specification["research_question"]) != cycle.question_digest:
        raise HTTPException(status_code=422, detail="Hypothesis question does not match cycle.")
    cycle.hypothesis_id = hypothesis.id
    cycle.task_id = task.id
    cycle.status = "registered"
    refresh_cycle(db, cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


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
        count = db.scalar(
            select(func.count(ResearchDailyCycle.id)).where(
                ResearchDailyCycle.program_id == program.id
            )
        ) or 0
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
    completed = [item for item in cycles if refresh_cycle(db, item).status == "completed"]
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
        "duplicate_work_avoided": sum(item.status == "duplicate_avoided" for item in cycles),
        "negative_results_retained": negative,
        "reproduction_rate": sum(reproductions) / len(reproductions) if reproductions else 0.0,
        "trial_adjusted_survivor_rate": accepted / trial_count if trial_count else 0.0,
        "median_seconds_to_registered_experiment": statistics.median(durations) if durations else None,
        "terminal_babysitting_events": sum(item.status == "attention_required" for item in cycles),
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
