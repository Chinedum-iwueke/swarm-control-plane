from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FounderNotification
from app.models.fleet import ResearchUtilizationSnapshot
from app.schemas.research_utilization import ResearchUtilizationSnapshotCreate
from app.services.founder_notifications import _insert_once

STALE_AFTER = timedelta(minutes=5)
ALERT_AFTER_SAMPLES = 3
ALERT_STATES = {"eligible_queue_empty", "resource_blocked", "work_queued"}


def record_snapshot(
    db: Session, payload: ResearchUtilizationSnapshotCreate
) -> ResearchUtilizationSnapshot:
    existing = db.scalar(
        select(ResearchUtilizationSnapshot).where(
            ResearchUtilizationSnapshot.machine == payload.machine,
            ResearchUtilizationSnapshot.sample_id == payload.sample_id,
        )
    )
    if existing is not None:
        return existing
    latest = db.scalar(
        select(ResearchUtilizationSnapshot)
        .where(ResearchUtilizationSnapshot.machine == payload.machine)
        .order_by(
            ResearchUtilizationSnapshot.observed_at.desc(),
            ResearchUtilizationSnapshot.id.desc(),
        )
        .limit(1)
    )
    document = payload.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    snapshot = ResearchUtilizationSnapshot(
        machine=payload.machine,
        sample_id=payload.sample_id,
        observed_at=payload.observed_at,
        state=payload.state,
        worker_budget=payload.worker_budget,
        active_workers=payload.active_workers,
        queue_counts=payload.queue_counts,
        work_kind_counts=payload.work_kind_counts,
        allocations=[item.model_dump(mode="json") for item in payload.allocations],
        scheduler=payload.scheduler.model_dump(mode="json"),
        source_commits=payload.source_commits,
        snapshot=document,
        record_digest=digest,
    )
    db.add(snapshot)
    db.flush()
    if latest is None or payload.observed_at > latest.observed_at:
        _reconcile_alert(db, snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def current_status(db: Session, machine: str | None = None) -> dict:
    latest_statement = select(
        ResearchUtilizationSnapshot.machine,
        func.max(ResearchUtilizationSnapshot.observed_at).label("observed_at"),
    )
    if machine:
        latest_statement = latest_statement.where(
            ResearchUtilizationSnapshot.machine == machine
        )
    latest = latest_statement.group_by(ResearchUtilizationSnapshot.machine).subquery()
    statement = select(ResearchUtilizationSnapshot).join(
        latest,
        (ResearchUtilizationSnapshot.machine == latest.c.machine)
        & (ResearchUtilizationSnapshot.observed_at == latest.c.observed_at),
    )
    rows = db.scalars(
        statement.order_by(
            ResearchUtilizationSnapshot.machine,
            ResearchUtilizationSnapshot.id.desc(),
        )
    ).all()
    current: dict[str, ResearchUtilizationSnapshot] = {}
    for row in rows:
        current.setdefault(row.machine, row)
    now = datetime.now(UTC)
    items = []
    for row in sorted(current.values(), key=lambda item: item.machine):
        age = max(0.0, (now - row.observed_at).total_seconds())
        items.append(
            {
                "id": row.id,
                "machine": row.machine,
                "observed_at": row.observed_at,
                "fresh": age <= STALE_AFTER.total_seconds(),
                "age_seconds": round(age, 3),
                "state": row.state,
                "worker_budget": row.worker_budget,
                "active_workers": row.active_workers,
                "idle_workers": max(0, row.worker_budget - row.active_workers),
                "queue_counts": row.queue_counts,
                "work_kind_counts": row.work_kind_counts,
                "allocations": row.allocations,
                "scheduler": row.scheduler,
                "source_commits": row.source_commits,
                "record_digest": row.record_digest,
            }
        )
    return {
        "generated_at": now,
        "items": items,
        "claim_boundary": (
            "Utilization snapshots report native queue custody and worker allocation. "
            "They do not establish research validity, promotion, shadow admission, or capital authority."
        ),
    }


def _reconcile_alert(db: Session, snapshot: ResearchUtilizationSnapshot) -> None:
    if snapshot.state not in ALERT_STATES:
        pending = list(
            db.scalars(
                select(FounderNotification).where(
                    FounderNotification.kind == "research_utilization_alert",
                    FounderNotification.state == "pending",
                )
            ).all()
        )
        now = datetime.now(UTC)
        for notification in pending:
            if (notification.payload or {}).get("machine") == snapshot.machine:
                notification.state = "superseded"
                notification.superseded_at = now
                notification.updated_at = now
        return
    recent = list(
        db.scalars(
            select(ResearchUtilizationSnapshot)
            .where(ResearchUtilizationSnapshot.machine == snapshot.machine)
            .order_by(
                ResearchUtilizationSnapshot.observed_at.desc(),
                ResearchUtilizationSnapshot.id.desc(),
            )
            .limit(ALERT_AFTER_SAMPLES)
        ).all()
    )
    if len(recent) < ALERT_AFTER_SAMPLES or any(
        item.state != snapshot.state for item in recent
    ):
        return
    prior_state = db.scalar(
        select(ResearchUtilizationSnapshot)
        .where(
            ResearchUtilizationSnapshot.machine == snapshot.machine,
            ResearchUtilizationSnapshot.state != snapshot.state,
            ResearchUtilizationSnapshot.observed_at <= recent[-1].observed_at,
        )
        .order_by(
            ResearchUtilizationSnapshot.observed_at.desc(),
            ResearchUtilizationSnapshot.id.desc(),
        )
        .limit(1)
    )
    episode = str(prior_state.id) if prior_state is not None else "initial"
    _insert_once(
        db,
        FounderNotification(
            kind="research_utilization_alert",
            entity_id=snapshot.id,
            deduplication_key=(
                f"research-utilization:{snapshot.machine}:{snapshot.state}:"
                f"{episode}"
            ),
            state="pending",
            payload={
                "machine": snapshot.machine,
                "state": snapshot.state,
                "summary": _alert_summary(snapshot.state),
                "worker_budget": snapshot.worker_budget,
                "active_workers": snapshot.active_workers,
                "queue_counts": snapshot.queue_counts,
                "observed_at": snapshot.observed_at.isoformat(),
                "record_digest": snapshot.record_digest,
                "action_authority": False,
            },
        ),
    )


def _alert_summary(state: str) -> str:
    return {
        "eligible_queue_empty": "No governed backtest or fallback research is eligible to run.",
        "resource_blocked": "Eligible research is blocked by the bounded compute policy.",
        "work_queued": "Eligible research is queued but no capacity job has acquired it.",
    }[state]
