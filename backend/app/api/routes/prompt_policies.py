import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.prompt_policy import PromptPolicyBundle
from app.schemas.prompt_policy import (
    PromptPolicyAction,
    PromptPolicyBundleCreate,
    PromptPolicyBundleResponse,
    PromptPolicyEvaluationCreate,
    PromptPolicyEvaluationResponse,
)
from app.services.prompt_policy import create_bundle, evaluate, promote, serialize

router = APIRouter(
    prefix="/v1/prompt-policies",
    tags=["prompt-policy-registry"],
    dependencies=[Depends(require_orchestrator)],
)


def locked(db: Session, bundle_id: uuid.UUID) -> PromptPolicyBundle:
    bundle = db.scalar(
        select(PromptPolicyBundle)
        .where(PromptPolicyBundle.id == bundle_id)
        .with_for_update()
    )
    if bundle is None:
        raise HTTPException(404, "Prompt-policy bundle not found.")
    return bundle


@router.post(
    "", response_model=PromptPolicyBundleResponse, status_code=status.HTTP_201_CREATED
)
def create(payload: PromptPolicyBundleCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        bundle = create_bundle(db, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bundle version or digest already exists.") from exc
    db.refresh(bundle)
    return serialize(db, bundle)


@router.get("", response_model=list[PromptPolicyBundleResponse])
def list_bundles(db: Annotated[Session, Depends(get_db)]):
    bundles = db.scalars(
        select(PromptPolicyBundle)
        .order_by(PromptPolicyBundle.created_at.desc())
        .limit(100)
    ).all()
    return [serialize(db, bundle) for bundle in bundles]


@router.get("/{bundle_id}", response_model=PromptPolicyBundleResponse)
def get(bundle_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    bundle = db.get(PromptPolicyBundle, bundle_id)
    if bundle is None:
        raise HTTPException(404, "Prompt-policy bundle not found.")
    return serialize(db, bundle)


@router.post("/{bundle_id}/evaluate", response_model=PromptPolicyEvaluationResponse)
def run_evaluation(
    bundle_id: uuid.UUID,
    payload: PromptPolicyEvaluationCreate,
    db: Annotated[Session, Depends(get_db)],
):
    bundle = locked(db, bundle_id)
    try:
        item = evaluate(db, bundle, payload)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "This exact evaluation fixture was already recorded."
        ) from exc
    return PromptPolicyEvaluationResponse(
        accepted=not item.violations,
        evaluation_id=item.id,
        receipt_digest=item.receipt_digest,
        violations=item.violations,
    )


@router.post("/{bundle_id}/promote/{target}", response_model=PromptPolicyBundleResponse)
def promote_bundle(
    bundle_id: uuid.UUID,
    target: str,
    payload: PromptPolicyAction,
    db: Annotated[Session, Depends(get_db)],
):
    bundle = locked(db, bundle_id)
    promote(db, bundle, payload.actor, target, payload.reason)
    db.commit()
    db.refresh(bundle)
    return serialize(db, bundle)
