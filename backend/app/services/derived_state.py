from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.models.curriculum import (
    ResearchBrainEvaluation,
    ResearchCurriculumPortfolio,
    ResearchDomainCurriculum,
)
from app.models.derived_state import (
    DerivedStateChange,
    DerivedStatePhaseReceipt,
    DerivedStateReconciliation,
)
from app.models.graph import EvidenceGraphProjectionState
from app.models.retrieval import EvidenceRetrievalState
from app.schemas.curriculum import (
    BrainEvaluationCreate,
    CurriculumPortfolioCreate,
    DomainCurriculumCreate,
)
from app.schemas.operation import OperationWrite
from app.services.curriculum import (
    evaluate_curriculum,
    register_curriculum,
    register_curriculum_portfolio,
)
from app.services.graph import (
    PROJECTION_NAME as GRAPH_PROJECTION_NAME,
)
from app.services.graph import (
    build_graph_projection,
    graph_projection_status,
    update_graph_projection_incrementally,
)
from app.services.operations import canonical_digest, upsert_operation
from app.services.retrieval import (
    PROJECTION_NAME as RETRIEVAL_PROJECTION_NAME,
)
from app.services.retrieval import (
    build_projections,
    freshness_snapshot,
    projection_status,
    update_projections_incrementally,
)

_LOCK_ID = 6_484_921_105_016_016
_DELTA_OBJECT_LIMIT = 5_000
_PHASES = ("retrieval", "graph", "curricula", "verify")
_TERMINAL = {"succeeded", "needs_attention"}
_RUN_STALE_AFTER = timedelta(minutes=10)


def schedule_reconciliation(
    db: Session,
    *,
    requested_by: str,
    force_full: bool = False,
) -> DerivedStateReconciliation | None:
    _lock(db)
    current = db.scalar(
        select(DerivedStateReconciliation)
        .where(DerivedStateReconciliation.state.in_(("queued", "running")))
        .order_by(DerivedStateReconciliation.created_at)
    )
    if current is not None:
        return current
    retryable = db.scalar(
        select(DerivedStateReconciliation)
        .where(
            DerivedStateReconciliation.state == "failed",
            DerivedStateReconciliation.retryable.is_(True),
        )
        .order_by(DerivedStateReconciliation.updated_at)
    )
    if retryable is not None:
        return retryable
    _, target_epoch = freshness_snapshot(db)
    retrieval = db.get(EvidenceRetrievalState, RETRIEVAL_PROJECTION_NAME)
    graph = db.get(EvidenceGraphProjectionState, GRAPH_PROJECTION_NAME)
    curriculum_state_digest, has_curricula = _curriculum_state_digest(db)
    latest = db.scalar(
        select(DerivedStateReconciliation).order_by(
            DerivedStateReconciliation.created_at.desc()
        )
    )
    pending = list(
        db.scalars(
            select(DerivedStateChange)
            .where(DerivedStateChange.reconciliation_id.is_(None))
            .order_by(DerivedStateChange.id)
        ).all()
    )
    states_current = (
        retrieval is not None
        and graph is not None
        and retrieval.source_epoch == target_epoch
        and graph.source_epoch == target_epoch
    )
    curricula_current = not has_curricula or (
        latest is not None
        and latest.state == "succeeded"
        and latest.source_epoch_target == target_epoch
        and latest.phase_results.get("curricula", {}).get("state_digest")
        == curriculum_state_digest
    )
    if not pending and states_current and curricula_current and not force_full:
        return None
    changed_ids = sorted(
        {object_id for change in pending for object_id in change.affected_object_ids}
    )
    projects = sorted({change.project for change in pending})
    starts = [state.source_epoch for state in (retrieval, graph) if state is not None]
    start_epoch = min(starts) if starts else 0
    strategy = select_strategy(
        force_full=force_full,
        ledger_epochs=[change.source_epoch for change in pending],
        source_epoch_start=start_epoch,
        source_epoch_target=target_epoch,
        projection_states_exist=retrieval is not None and graph is not None,
        changed_object_count=len(changed_ids),
    )
    material = {
        "source_epoch_start": start_epoch,
        "source_epoch_target": target_epoch,
        "changed_object_ids": changed_ids,
        "affected_projects": projects,
        "strategy": strategy,
        "curriculum_state_digest": curriculum_state_digest,
    }
    input_digest = canonical_digest(material)
    existing = db.scalar(
        select(DerivedStateReconciliation).where(
            DerivedStateReconciliation.input_digest == input_digest
        )
    )
    if existing is not None:
        return existing
    run = DerivedStateReconciliation(
        id=uuid.uuid4(),
        source_epoch_start=start_epoch,
        source_epoch_target=target_epoch,
        state="queued",
        phase="queued",
        strategy=strategy,
        requested_by=requested_by,
        attempt_count=0,
        max_attempts=3,
        changed_object_ids=changed_ids,
        affected_projects=projects,
        affected_domains=[],
        phase_results={},
        timings_ms={},
        input_digest=input_digest,
        terminal_digest=None,
        error_summary=None,
        retryable=True,
        heartbeat_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    for change in pending:
        change.reconciliation_id = run.id
    db.commit()
    db.refresh(run)
    _publish_operation(db, run, "created")
    return run


def execute_reconciliation(db: Session, run_id: UUID) -> DerivedStateReconciliation:
    _lock(db)
    run = db.get(DerivedStateReconciliation, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Derived-state run not found.")
    if run.state in _TERMINAL:
        return run
    if (
        run.state == "running"
        and run.heartbeat_at >= datetime.now(UTC) - _RUN_STALE_AFTER
    ):
        return run
    if run.attempt_count >= run.max_attempts:
        raise HTTPException(
            status_code=409, detail="Derived-state retry budget exhausted."
        )
    run.state = "running"
    run.attempt_count += 1
    run.started_at = run.started_at or datetime.now(UTC)
    run.error_summary = None
    run.heartbeat_at = datetime.now(UTC)
    db.commit()
    _publish_operation(db, run, "started")
    try:
        for phase in _PHASES:
            if _receipt(db, run.id, phase) is not None:
                continue
            run = db.get(DerivedStateReconciliation, run.id)
            run.phase = phase
            run.heartbeat_at = datetime.now(UTC)
            db.commit()
            _publish_operation(db, run, "progress")
            started = time.perf_counter()
            detail = _execute_phase(db, run, phase)
            elapsed = round((time.perf_counter() - started) * 1000, 3)
            _record_phase(db, run, phase, detail, elapsed)
        run = db.get(DerivedStateReconciliation, run.id)
        attention = any(
            item.get("status") in {"awaiting_rebaseline", "gaps_detected"}
            for item in run.phase_results.get("curricula", {}).get("domains", [])
        )
        run.state = "needs_attention" if attention else "succeeded"
        run.phase = "complete"
        run.retryable = False
        run.completed_at = datetime.now(UTC)
        run.heartbeat_at = run.completed_at
        run.terminal_digest = canonical_digest(
            {
                "input_digest": run.input_digest,
                "state": run.state,
                "phase_results": run.phase_results,
                "timings_ms": run.timings_ms,
            }
        )
        db.commit()
        db.refresh(run)
        _publish_operation(db, run, "succeeded")
        return run
    except Exception as exc:
        db.rollback()
        run = db.get(DerivedStateReconciliation, run_id)
        run.state = "failed"
        run.phase = "failed"
        run.error_summary = f"{type(exc).__name__}: {str(exc)[:3900]}"
        moved = (
            isinstance(exc, HTTPException)
            and exc.status_code == 409
            and any(
                marker in str(exc.detail).lower()
                for marker in ("changed during", "snapshot moved", "did not converge")
            )
        )
        run.retryable = not moved and run.attempt_count < run.max_attempts
        run.heartbeat_at = datetime.now(UTC)
        db.commit()
        _publish_operation(db, run, "failed")
        raise


def reconcile_once(db: Session, requested_by: str) -> DerivedStateReconciliation | None:
    run = db.scalar(
        select(DerivedStateReconciliation)
        .where(
            DerivedStateReconciliation.state == "failed",
            DerivedStateReconciliation.retryable.is_(True),
        )
        .order_by(DerivedStateReconciliation.updated_at)
    )
    if run is None:
        run = schedule_reconciliation(db, requested_by=requested_by)
    return execute_reconciliation(db, run.id) if run is not None else None


def derived_state_status(db: Session) -> dict[str, Any]:
    _, epoch = freshness_snapshot(db)
    pending = int(
        db.scalar(
            select(func.count())
            .select_from(DerivedStateChange)
            .where(DerivedStateChange.reconciliation_id.is_(None))
        )
        or 0
    )
    retrieval = _projection_summary(db, "retrieval")
    graph = _projection_summary(db, "graph")
    latest = db.scalar(
        select(DerivedStateReconciliation).order_by(
            DerivedStateReconciliation.created_at.desc()
        )
    )
    curriculum_state_digest, has_curricula = _curriculum_state_digest(db)
    curricula_current = not has_curricula or (
        latest is not None
        and latest.state == "succeeded"
        and latest.source_epoch_target == epoch
        and latest.phase_results.get("curricula", {}).get("state_digest")
        == curriculum_state_digest
    )
    return {
        "corpus_epoch": epoch,
        "pending_changes": pending,
        "retrieval": retrieval,
        "graph": graph,
        "current": (
            pending == 0
            and retrieval.get("source_epoch") == epoch
            and graph.get("source_epoch") == epoch
            and curricula_current
        ),
        "latest_run": latest,
        "claim_boundary": (
            "Canonical evidence remains authoritative. Derived readiness is current "
            "only when retrieval and graph epochs match the corpus and curriculum "
            "impacts have a terminal receipt."
        ),
    }


def _execute_phase(
    db: Session, run: DerivedStateReconciliation, phase: str
) -> dict[str, Any]:
    _, current_epoch = freshness_snapshot(db)
    if current_epoch != run.source_epoch_target:
        raise HTTPException(
            status_code=409,
            detail="Canonical evidence changed during derived-state reconciliation.",
        )
    if phase == "retrieval":
        state = db.get(EvidenceRetrievalState, RETRIEVAL_PROJECTION_NAME)
        if run.strategy == "full":
            state = build_projections(db, progress=_heartbeat_callback(db, run.id))
            strategy = "full"
        elif state is not None and state.source_epoch == current_epoch:
            strategy = "reused"
        elif state is not None:
            state = update_projections_incrementally(
                db,
                {UUID(value) for value in run.changed_object_ids},
                expected_epoch=current_epoch,
            )
            strategy = "incremental"
        else:  # Defensive: scheduling selects full when no prior state exists.
            raise HTTPException(status_code=409, detail="Retrieval baseline is absent.")
        return {
            "strategy": strategy,
            "source_epoch": state.source_epoch,
            "corpus_digest": state.corpus_digest,
            "object_count": state.object_count,
            "projection_digest": canonical_digest(
                {
                    "name": state.projection_name,
                    "version": state.projection_version,
                    "corpus_digest": state.corpus_digest,
                    "source_epoch": state.source_epoch,
                    "object_count": state.object_count,
                }
            ),
        }
    if phase == "graph":
        state = db.get(EvidenceGraphProjectionState, GRAPH_PROJECTION_NAME)
        if run.strategy == "full":
            state = build_graph_projection(db, progress=_heartbeat_callback(db, run.id))
            strategy = "full"
        elif state is not None and state.source_epoch == current_epoch:
            strategy = "reused"
        elif state is not None:
            state = update_graph_projection_incrementally(
                db,
                {UUID(value) for value in run.changed_object_ids},
                expected_epoch=current_epoch,
            )
            strategy = "incremental"
        else:  # Defensive: scheduling selects full when no prior state exists.
            raise HTTPException(status_code=409, detail="Graph baseline is absent.")
        return {
            "strategy": strategy,
            "source_epoch": state.source_epoch,
            "manifest_digest": state.manifest_digest,
            "node_count": state.node_count,
            "edge_count": state.edge_count,
            "projection_digest": state.manifest_digest,
        }
    if phase == "curricula":
        return _reconcile_curricula(db, run)
    if phase == "verify":
        retrieval, _, retrieval_stale = projection_status(db)
        graph, graph_stale = graph_projection_status(db)
        _, verified_epoch = freshness_snapshot(db)
        if (
            retrieval_stale
            or graph_stale
            or retrieval.source_epoch != verified_epoch
            or graph.source_epoch != verified_epoch
        ):
            raise HTTPException(
                status_code=409, detail="Derived projections did not converge."
            )
        return {
            "source_epoch": verified_epoch,
            "retrieval_current": True,
            "graph_current": True,
            "retrieval_digest": retrieval.corpus_digest,
            "graph_digest": graph.manifest_digest,
        }
    raise RuntimeError(f"Unknown derived-state phase: {phase}")


def _reconcile_curricula(
    db: Session, run: DerivedStateReconciliation
) -> dict[str, Any]:
    records = list(
        db.scalars(
            select(ResearchDomainCurriculum).order_by(
                ResearchDomainCurriculum.domain_key,
                ResearchDomainCurriculum.created_at.desc(),
            )
        ).all()
    )
    latest_by_domain: dict[str, ResearchDomainCurriculum] = {}
    for record in records:
        latest_by_domain.setdefault(record.domain_key, record)
    outcomes = []
    refreshed = []
    current_corpus, _ = freshness_snapshot(db)
    graph_state, _ = graph_projection_status(db)
    for domain, curriculum in latest_by_domain.items():
        evaluation = db.scalar(
            select(ResearchBrainEvaluation)
            .where(ResearchBrainEvaluation.curriculum_id == curriculum.id)
            .order_by(ResearchBrainEvaluation.evaluated_at.desc())
        )
        if (
            curriculum.corpus_digest == current_corpus
            and curriculum.graph_manifest_digest == graph_state.manifest_digest
            and evaluation is not None
            and evaluation.corpus_digest == current_corpus
            and evaluation.graph_manifest_digest == graph_state.manifest_digest
        ):
            refreshed.append(curriculum)
            outcomes.append(
                {
                    "domain": domain,
                    "status": evaluation.status,
                    "curriculum_id": str(curriculum.id),
                    "evaluation_id": str(evaluation.id),
                    "evaluation_digest": evaluation.record_digest,
                    "strategy": "reused",
                }
            )
            continue
        if evaluation is None or not evaluation.case_specifications:
            outcomes.append(
                {
                    "domain": domain,
                    "status": "awaiting_rebaseline",
                    "reason": "evaluation_case_specifications_unavailable",
                    "prior_curriculum_id": str(curriculum.id),
                }
            )
            continue
        version = _next_version(
            item.version for item in records if item.domain_key == domain
        )
        payload = DomainCurriculumCreate.model_validate(
            {
                "domain_key": curriculum.domain_key,
                "version": version,
                "title": curriculum.title,
                "project": curriculum.project,
                **curriculum.specification,
                "created_by": "derived-state-orchestrator",
            }
        )
        refreshed_curriculum = register_curriculum(db, payload)
        refreshed_evaluation = evaluate_curriculum(
            db,
            BrainEvaluationCreate.model_validate(
                {
                    "curriculum_id": refreshed_curriculum.id,
                    "evaluation_version": evaluation.evaluation_version,
                    "cases": evaluation.case_specifications,
                    "thresholds": evaluation.thresholds,
                    "evaluated_by": "derived-state-orchestrator",
                }
            ),
        )
        curriculum.status = "superseded"
        db.commit()
        refreshed.append(refreshed_curriculum)
        outcomes.append(
            {
                "domain": domain,
                "status": refreshed_evaluation.status,
                "curriculum_id": str(refreshed_curriculum.id),
                "evaluation_id": str(refreshed_evaluation.id),
                "evaluation_digest": refreshed_evaluation.record_digest,
            }
        )
    run = db.get(DerivedStateReconciliation, run.id)
    run.affected_domains = sorted(latest_by_domain)
    db.commit()
    portfolio = _rebuild_portfolio(db, refreshed) if refreshed else None
    state_digest, _ = _curriculum_state_digest(db)
    return {
        "source_epoch": run.source_epoch_target,
        "domains": outcomes,
        "affected_domain_count": len(outcomes),
        "portfolio_id": str(portfolio.id) if portfolio else None,
        "portfolio_status": portfolio.status if portfolio else None,
        "state_digest": state_digest,
    }


def _rebuild_portfolio(
    db: Session,
    refreshed: list[ResearchDomainCurriculum],
) -> ResearchCurriculumPortfolio | None:
    latest = db.scalar(
        select(ResearchCurriculumPortfolio).order_by(
            ResearchCurriculumPortfolio.created_at.desc()
        )
    )
    if latest is None:
        return None
    replacements = {item.domain_key: item for item in refreshed}
    selected = []
    for domain, old_id in zip(
        latest.required_domain_keys, latest.curriculum_ids, strict=True
    ):
        selected.append(
            replacements.get(domain)
            or db.get(ResearchDomainCurriculum, UUID(str(old_id)))
        )
    return register_curriculum_portfolio(
        db,
        CurriculumPortfolioCreate(
            portfolio_key=latest.portfolio_key,
            version=_next_version(
                item.version
                for item in db.scalars(select(ResearchCurriculumPortfolio)).all()
                if item.portfolio_key == latest.portfolio_key
            ),
            required_domain_keys=list(latest.required_domain_keys),
            curriculum_ids=[item.id for item in selected],
            created_by="derived-state-orchestrator",
        ),
    )


def _record_phase(
    db: Session,
    run: DerivedStateReconciliation,
    phase: str,
    detail: dict[str, Any],
    elapsed_ms: float,
) -> None:
    now = datetime.now(UTC)
    output_digest = canonical_digest(detail)
    db.add(
        DerivedStatePhaseReceipt(
            reconciliation_id=run.id,
            phase=phase,
            status="succeeded",
            input_digest=run.input_digest,
            output_digest=output_digest,
            detail=detail,
            started_at=now,
            completed_at=now,
        )
    )
    run = db.get(DerivedStateReconciliation, run.id)
    run.phase_results = {**run.phase_results, phase: detail}
    run.timings_ms = {**run.timings_ms, phase: elapsed_ms}
    run.heartbeat_at = now
    db.commit()


def _receipt(db: Session, run_id: UUID, phase: str) -> DerivedStatePhaseReceipt | None:
    return db.scalar(
        select(DerivedStatePhaseReceipt).where(
            DerivedStatePhaseReceipt.reconciliation_id == run_id,
            DerivedStatePhaseReceipt.phase == phase,
        )
    )


def _projection_summary(db: Session, kind: str) -> dict[str, Any]:
    try:
        if kind == "retrieval":
            state, _, stale = projection_status(db)
            return {
                "source_epoch": state.source_epoch,
                "digest": state.corpus_digest,
                "stale": stale,
            }
        state, stale = graph_projection_status(db)
        return {
            "source_epoch": state.source_epoch,
            "digest": state.manifest_digest,
            "stale": stale,
        }
    except HTTPException:
        return {"source_epoch": None, "digest": None, "stale": True}


def _publish_operation(
    db: Session, run: DerivedStateReconciliation, event_type: str
) -> None:
    terminal = run.state in _TERMINAL | {"failed"}
    state = "blocked" if run.state == "needs_attention" else run.state
    upsert_operation(
        db,
        OperationWrite(
            operation_key=f"derived-state:{run.id}",
            kind="research_derived_state_reconciliation",
            title="Reconcile Research Intelligence derived state",
            project="systematic-research",
            machine="vm2-deployment",
            owner_type="service",
            owner_id="derived-state-orchestrator",
            state=state,
            phase=run.phase,
            progress_mode="determinate",
            progress_current=(
                len(_PHASES)
                if terminal
                else sum(phase in run.phase_results for phase in _PHASES)
            ),
            progress_total=len(_PHASES),
            progress_unit="phases",
            retryable=run.retryable,
            error_summary=run.error_summary,
            links={
                "derived_state_run_id": str(run.id),
                "surface": "research-intelligence",
            },
            detail={
                "source_epoch_start": run.source_epoch_start,
                "source_epoch_target": run.source_epoch_target,
                "strategy": run.strategy,
                "attention_required": run.state == "needs_attention",
            },
            input_digest=run.input_digest,
        ),
        actor="derived-state-orchestrator",
        event_type=event_type,
    )


def _next_version(versions) -> str:
    parsed = [tuple(map(int, value.split("."))) for value in versions]
    major, minor, patch = max(parsed or [(1, 0, -1)])
    return f"{major}.{minor}.{patch + 1}"


def _curriculum_state_digest(db: Session) -> tuple[str, bool]:
    curricula = list(
        db.execute(
            select(
                ResearchDomainCurriculum.id,
                ResearchDomainCurriculum.domain_key,
                ResearchDomainCurriculum.version,
                ResearchDomainCurriculum.status,
                ResearchDomainCurriculum.record_digest,
            ).order_by(ResearchDomainCurriculum.id)
        )
    )
    evaluations = list(
        db.execute(
            select(
                ResearchBrainEvaluation.id,
                ResearchBrainEvaluation.curriculum_id,
                ResearchBrainEvaluation.status,
                ResearchBrainEvaluation.record_digest,
            ).order_by(ResearchBrainEvaluation.id)
        )
    )
    portfolios = list(
        db.execute(
            select(
                ResearchCurriculumPortfolio.id,
                ResearchCurriculumPortfolio.version,
                ResearchCurriculumPortfolio.status,
                ResearchCurriculumPortfolio.record_digest,
            ).order_by(ResearchCurriculumPortfolio.id)
        )
    )
    material = {
        "curricula": [tuple(map(str, row)) for row in curricula],
        "evaluations": [tuple(map(str, row)) for row in evaluations],
        "portfolios": [tuple(map(str, row)) for row in portfolios],
    }
    return canonical_digest(material), bool(curricula)


def select_strategy(
    *,
    force_full: bool,
    ledger_epochs: list[int],
    source_epoch_start: int,
    source_epoch_target: int,
    projection_states_exist: bool,
    changed_object_count: int,
) -> str:
    observed_epochs = set(ledger_epochs)
    complete_ledger = observed_epochs.issuperset(
        range(source_epoch_start + 1, source_epoch_target + 1)
    )
    if (
        not force_full
        and complete_ledger
        and projection_states_exist
        and changed_object_count <= _DELTA_OBJECT_LIMIT
    ):
        return "incremental"
    return "full"


def _lock(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_ID})


def _heartbeat_callback(db: Session, run_id: UUID):
    engine = db.get_bind()

    def heartbeat(_phase: str, _current: int, _total: int, _unit: str) -> None:
        with engine.begin() as connection:
            connection.execute(
                update(DerivedStateReconciliation)
                .where(DerivedStateReconciliation.id == run_id)
                .values(heartbeat_at=datetime.now(UTC))
            )

    return heartbeat
