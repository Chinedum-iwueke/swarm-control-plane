from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.laboratory import (
    LaboratoryPublicationCreate,
    LaboratoryPublicationEventResponse,
    LaboratoryPublicationResponse,
    LaboratoryReplayResponse,
    MemoryReceiptCreate,
    ProjectionReceiptCreate,
    PublicationFailureCreate,
)
from app.services.laboratory import (
    create_publication,
    get_publication,
    publication_events,
    record_failure,
    record_memory_receipt,
    record_projection_receipt,
)

router = APIRouter(
    prefix="/v1/research/laboratory/publications",
    tags=["research-laboratory"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("", response_model=LaboratoryPublicationResponse, status_code=201)
def publish(
    payload: LaboratoryPublicationCreate, db: Annotated[Session, Depends(get_db)]
):
    return LaboratoryPublicationResponse.model_validate(
        create_publication(db, payload), from_attributes=True
    )


@router.get("/{publication_id}", response_model=LaboratoryPublicationResponse)
def read(publication_id: UUID, db: Annotated[Session, Depends(get_db)]):
    return LaboratoryPublicationResponse.model_validate(
        get_publication(db, publication_id), from_attributes=True
    )


@router.post(
    "/{publication_id}/projections", response_model=LaboratoryPublicationResponse
)
def confirm_projections(
    publication_id: UUID,
    payload: ProjectionReceiptCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return LaboratoryPublicationResponse.model_validate(
        record_projection_receipt(db, publication_id, payload), from_attributes=True
    )


@router.post("/{publication_id}/memory", response_model=LaboratoryPublicationResponse)
def confirm_memory(
    publication_id: UUID,
    payload: MemoryReceiptCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return LaboratoryPublicationResponse.model_validate(
        record_memory_receipt(db, publication_id, payload), from_attributes=True
    )


@router.post("/{publication_id}/failures", response_model=LaboratoryPublicationResponse)
def fail(
    publication_id: UUID,
    payload: PublicationFailureCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return LaboratoryPublicationResponse.model_validate(
        record_failure(db, publication_id, payload), from_attributes=True
    )


@router.get("/{publication_id}/replay", response_model=LaboratoryReplayResponse)
def replay(publication_id: UUID, db: Annotated[Session, Depends(get_db)]):
    record = get_publication(db, publication_id)
    response = LaboratoryPublicationResponse.model_validate(
        record, from_attributes=True
    ).model_dump()
    response["events"] = [
        LaboratoryPublicationEventResponse.model_validate(item, from_attributes=True)
        for item in publication_events(db, publication_id)
    ]
    return LaboratoryReplayResponse.model_validate(response)
