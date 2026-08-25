from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.schemas.lifecycle_consequence import (
    ConsequenceCreate,
    ConsequenceListResponse,
    ConsequenceResponse,
    ConsequenceReverse,
)
from app.services.lifecycle_consequence import (
    apply_consequence,
    expire_consequence,
    list_consequences,
    reverse_consequence,
)

router = APIRouter(
    prefix="/v1/lifecycle-consequences",
    tags=["lifecycle-consequences"],
    dependencies=[Depends(require_orchestrator)],
)


@router.get("", response_model=ConsequenceListResponse)
def read_consequences(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    items = list_consequences(db, limit)
    return ConsequenceListResponse(items=items, count=len(items))


@router.post(
    "/subjects/{subject_type}/{subject_id}",
    response_model=ConsequenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_consequence(
    subject_type: str,
    subject_id: str,
    payload: ConsequenceCreate,
    db: Annotated[Session, Depends(get_db)],
):
    return apply_consequence(db, subject_type, subject_id, payload)


@router.post(
    "/{consequence_id}/reverse",
    response_model=ConsequenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def reverse(
    consequence_id: UUID,
    payload: ConsequenceReverse,
    db: Annotated[Session, Depends(get_db)],
):
    return reverse_consequence(db, consequence_id, payload)


@router.post(
    "/{consequence_id}/expire",
    response_model=ConsequenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def expire(
    consequence_id: UUID,
    payload: ConsequenceReverse,
    db: Annotated[Session, Depends(get_db)],
):
    return expire_consequence(db, consequence_id, payload)
