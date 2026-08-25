from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.governance_audit import GovernanceAuditExport
from app.schemas.governance_audit import (
    GovernanceAuditExportCreate,
    GovernanceAuditExportResponse,
    GovernanceAuditVerifyRequest,
    GovernanceAuditVerifyResponse,
)
from app.services.governance_audit import create_export, verify_bundle

router = APIRouter(
    prefix="/v1/governance-audit",
    tags=["governance-audit"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post(
    "/exports",
    response_model=GovernanceAuditExportResponse,
    status_code=status.HTTP_201_CREATED,
)
def export(
    payload: GovernanceAuditExportCreate, db: Annotated[Session, Depends(get_db)]
):
    return create_export(
        db, payload.requested_by, get_settings().package_signing_secret
    )


@router.get("/exports/{export_id}", response_model=GovernanceAuditExportResponse)
def read_export(export_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = db.get(GovernanceAuditExport, export_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="Governance audit export not found."
        )
    return record


@router.post("/verify", response_model=GovernanceAuditVerifyResponse)
def verify(payload: GovernanceAuditVerifyRequest):
    return verify_bundle(payload.bundle)
