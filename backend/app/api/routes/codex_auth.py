import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import CodexAuthRecovery
from app.schemas.codex_auth import (
    CodexAuthRecoveryReport,
    CodexAuthRecoveryResponse,
    CodexAuthRecoveryRetry,
)
from app.services.codex_auth import report_recovery, request_retry

router = APIRouter(
    prefix="/v1/codex-auth",
    tags=["codex-auth"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("/recoveries", response_model=list[CodexAuthRecoveryResponse])
def list_recoveries(
    db: Annotated[Session, Depends(get_db)],
    runtime_key: Annotated[str | None, Query(max_length=120)] = None,
) -> list[CodexAuthRecoveryResponse]:
    statement = select(CodexAuthRecovery).order_by(CodexAuthRecovery.runtime_key)
    if runtime_key:
        statement = statement.where(CodexAuthRecovery.runtime_key == runtime_key)
    return [
        CodexAuthRecoveryResponse.model_validate(item)
        for item in db.scalars(statement).all()
    ]


@router.post("/recoveries/report", response_model=CodexAuthRecoveryResponse)
def report(
    payload: CodexAuthRecoveryReport,
    db: Annotated[Session, Depends(get_db)],
) -> CodexAuthRecoveryResponse:
    recovery = report_recovery(db, payload, actor="codex-auth-watcher")
    db.commit()
    db.refresh(recovery)
    return CodexAuthRecoveryResponse.model_validate(recovery)


@router.post(
    "/recoveries/{recovery_id}/retry", response_model=CodexAuthRecoveryResponse
)
def retry(
    recovery_id: uuid.UUID,
    payload: CodexAuthRecoveryRetry,
    db: Annotated[Session, Depends(get_db)],
) -> CodexAuthRecoveryResponse:
    recovery = db.scalar(
        select(CodexAuthRecovery)
        .where(CodexAuthRecovery.id == recovery_id)
        .with_for_update()
    )
    if recovery is None:
        raise HTTPException(status_code=404, detail="Codex auth recovery not found.")
    request_retry(
        db,
        recovery,
        actor="founder-mission-control",
        reason=payload.reason,
    )
    db.commit()
    db.refresh(recovery)
    return CodexAuthRecoveryResponse.model_validate(recovery)
