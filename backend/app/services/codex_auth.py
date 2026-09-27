from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CodexAuthRecovery, CodexAuthRecoveryEvent, FounderNotification
from app.schemas.codex_auth import CodexAuthRecoveryReport


def report_recovery(
    db: Session, payload: CodexAuthRecoveryReport, *, actor: str
) -> CodexAuthRecovery:
    now = datetime.now(UTC)
    recovery = db.scalar(
        select(CodexAuthRecovery)
        .where(CodexAuthRecovery.runtime_key == payload.runtime_key)
        .with_for_update()
    )
    if recovery is None:
        recovery = CodexAuthRecovery(
            runtime_key=payload.runtime_key,
            state=payload.state,
            generation=payload.generation,
        )
        db.add(recovery)
        db.flush()
    if payload.generation < recovery.generation:
        raise HTTPException(status_code=409, detail="Stale Codex auth generation.")
    if payload.state == "awaiting_authorization":
        if not (
            payload.verification_uri
            and payload.device_code
            and payload.code_expires_at
            and payload.code_expires_at > now
            and payload.code_expires_at <= now + timedelta(minutes=20)
        ):
            raise HTTPException(
                status_code=422,
                detail="A live device code, URI, and expiry are required.",
            )
        if (
            payload.generation <= recovery.generation
            and recovery.state == payload.state
            and recovery.device_code != payload.device_code
        ):
            raise HTTPException(
                status_code=409,
                detail="Device code replacement requires a new generation.",
            )
        recovery.retry_acknowledged_at = now
    previous_state = recovery.state
    recovery.state = payload.state
    recovery.generation = payload.generation
    recovery.verification_uri = (
        str(payload.verification_uri) if payload.verification_uri else None
    )
    recovery.device_code = payload.device_code
    recovery.code_expires_at = payload.code_expires_at
    recovery.failure_summary = payload.failure_summary
    recovery.last_probe_at = now
    recovery.updated_at = now
    if payload.state == "healthy":
        recovery.authenticated_at = now
        recovery.verification_uri = None
        recovery.device_code = None
        recovery.code_expires_at = None
        recovery.retry_requested_at = None
        recovery.retry_acknowledged_at = None
        _supersede_notifications(db, recovery.id, now)
    elif payload.state == "awaiting_authorization":
        _notify_device_code(db, recovery, now)
    db.add(
        CodexAuthRecoveryEvent(
            recovery_id=recovery.id,
            event_type=(
                "state_reported" if previous_state == payload.state else "state_changed"
            ),
            generation=recovery.generation,
            actor=actor,
            payload={"state": recovery.state},
        )
    )
    db.flush()
    return recovery


def request_retry(
    db: Session, recovery: CodexAuthRecovery, *, actor: str, reason: str
) -> CodexAuthRecovery:
    now = datetime.now(UTC)
    if recovery.state == "healthy":
        raise HTTPException(status_code=409, detail="Codex authentication is healthy.")
    if recovery.retry_requested_at is not None and (
        recovery.retry_acknowledged_at is None
        or recovery.retry_acknowledged_at < recovery.retry_requested_at
    ):
        return recovery
    recovery.retry_requested_at = now
    recovery.updated_at = now
    db.add(
        CodexAuthRecoveryEvent(
            recovery_id=recovery.id,
            event_type="retry_requested",
            generation=recovery.generation,
            actor=actor,
            payload={"reason": reason},
        )
    )
    db.flush()
    return recovery


def _notify_device_code(
    db: Session, recovery: CodexAuthRecovery, now: datetime
) -> None:
    key = f"codex-auth:{recovery.id}:{recovery.generation}"
    notification = db.scalar(
        select(FounderNotification).where(FounderNotification.deduplication_key == key)
    )
    if notification is None:
        notification = FounderNotification(
            kind="codex_authentication_required",
            entity_id=recovery.id,
            deduplication_key=key,
            state="pending",
            payload={
                "recovery_id": str(recovery.id),
                "runtime_key": recovery.runtime_key,
                "generation": recovery.generation,
                "verification_uri": recovery.verification_uri,
                "device_code": recovery.device_code,
                "code_expires_at": recovery.code_expires_at.isoformat(),
            },
        )
        db.add(notification)
    notification.updated_at = now


def _supersede_notifications(db: Session, recovery_id, now: datetime) -> None:
    values = db.scalars(
        select(FounderNotification).where(
            FounderNotification.entity_id == recovery_id,
            FounderNotification.kind == "codex_authentication_required",
            FounderNotification.state.in_(["pending", "waiting"]),
        )
    ).all()
    for notification in values:
        notification.state = "superseded"
        notification.superseded_at = now
        notification.updated_at = now
