from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.corpus import CorpusSecurityFinding
from app.schemas.corpus import (
    CorpusBackupCreate,
    CorpusBackupResponse,
    CorpusHealthResponse,
    CorpusRestoreCreate,
    ProjectionRecoveryCreate,
    QueueRecoveryCreate,
    RecoveryRunResponse,
    SecurityFindingResponse,
)
from app.services.corpus import (
    corpus_health,
    create_backup,
    recover_projections,
    recover_queue,
    restore_backup,
)
from app.services.object_store import FilesystemEvidenceObjectStore

router = APIRouter(
    prefix="/v1/research/corpus",
    tags=["corpus-operations"],
    dependencies=[Depends(require_orchestrator)],
)


@lru_cache
def _store() -> FilesystemEvidenceObjectStore:
    return FilesystemEvidenceObjectStore(get_settings().evidence_object_root)


@router.get("/health", response_model=CorpusHealthResponse)
def read_corpus_health(
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[str, Query(pattern=r"^[a-z][a-z0-9._-]{0,99}$")],
):
    return corpus_health(db, project, _store())


@router.get("/security-findings", response_model=list[SecurityFindingResponse])
def read_security_findings(
    db: Annotated[Session, Depends(get_db)],
    project: Annotated[str, Query(pattern=r"^[a-z][a-z0-9._-]{0,99}$")],
):
    return list(
        db.scalars(
            select(CorpusSecurityFinding)
            .where(CorpusSecurityFinding.project == project)
            .order_by(CorpusSecurityFinding.recorded_at.desc())
        ).all()
    )


@router.post("/backups", response_model=CorpusBackupResponse, status_code=201)
def create_corpus_backup(
    payload: CorpusBackupCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return create_backup(db, payload, _store())


@router.post(
    "/backups/{backup_id}/restore",
    response_model=RecoveryRunResponse,
    status_code=201,
)
def restore_corpus_backup(
    backup_id: UUID,
    payload: CorpusRestoreCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return restore_backup(db, backup_id, _store(), payload.requested_by)


@router.post(
    "/projections/recover", response_model=RecoveryRunResponse, status_code=201
)
def rebuild_corpus_projections(
    payload: ProjectionRecoveryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return recover_projections(db, payload.project, payload.requested_by)


@router.post("/queue/recover", response_model=RecoveryRunResponse, status_code=201)
def recover_ingestion_queue(
    payload: QueueRecoveryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return recover_queue(
        db,
        payload.project,
        _store(),
        stale_after_seconds=payload.stale_after_seconds,
        requested_by=payload.requested_by,
    )
