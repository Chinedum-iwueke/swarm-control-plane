from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.evidence import (
    EvidenceLineageResponse,
    EvidenceObjectCreate,
    EvidenceObjectListResponse,
    EvidenceObjectResponse,
    EvidenceObjectType,
)
from app.services.evidence import (
    ORCHESTRATOR_ACCESS,
    evidence_response,
    get_evidence_lineage,
    get_evidence_object,
    list_evidence_objects,
    register_evidence_object,
)

router = APIRouter(
    prefix="/v1/research/evidence",
    tags=["canonical-evidence"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/objects", response_model=EvidenceObjectResponse, status_code=201)
def create_evidence_object(
    payload: EvidenceObjectCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return evidence_response(register_evidence_object(db, payload, ORCHESTRATOR_ACCESS))


@router.get("/objects/{object_id}", response_model=EvidenceObjectResponse)
def read_evidence_object(
    object_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    return evidence_response(get_evidence_object(db, object_id, ORCHESTRATOR_ACCESS))


@router.get("/objects", response_model=EvidenceObjectListResponse)
def read_evidence_objects(
    db: Annotated[Session, Depends(get_db)],
    object_type: EvidenceObjectType | None = None,
    project: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    records = list_evidence_objects(
        db,
        ORCHESTRATOR_ACCESS,
        object_type=object_type,
        project=project,
        limit=limit,
    )
    return EvidenceObjectListResponse(
        items=[evidence_response(item) for item in records],
        count=len(records),
    )


@router.get("/objects/{object_id}/lineage", response_model=EvidenceLineageResponse)
def read_evidence_lineage(
    object_id: UUID,
    db: Annotated[Session, Depends(get_db)],
):
    record, ancestors, descendants = get_evidence_lineage(
        db, object_id, ORCHESTRATOR_ACCESS
    )
    return EvidenceLineageResponse(
        object=evidence_response(record),
        ancestors=[evidence_response(item) for item in ancestors],
        descendants=[evidence_response(item) for item in descendants],
    )
