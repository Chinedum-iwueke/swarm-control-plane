from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models import RunbookPackage, RunbookPromotion
from app.schemas.runbook_package import (
    RunbookPackageCreate,
    RunbookPackageDetail,
    RunbookPackageResponse,
    RunbookPromotionCreate,
    RunbookPromotionResponse,
)
from app.services.runbook_packages import (
    promote_runbook_package,
    verify_runbook_package,
)

router = APIRouter(prefix="/v1/runbook-packages", tags=["runbook-packages"])


@router.post(
    "",
    dependencies=[Depends(require_orchestrator)],
    response_model=RunbookPackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_runbook_package(
    payload: RunbookPackageCreate,
    db: Annotated[Session, Depends(get_db)],
) -> RunbookPackageResponse:
    verify_runbook_package(payload, get_settings().package_signing_secret)
    package = RunbookPackage(
        name=payload.manifest.name,
        version=payload.manifest.version,
        manifest=payload.manifest.model_dump(mode="json"),
        manifest_digest=payload.manifest_digest,
        signature=payload.signature,
        source_repository=payload.source_repository,
        source_commit=payload.source_commit,
        created_by=payload.created_by,
    )
    db.add(package)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Runbook package name/version or digest already exists.",
        ) from exc
    db.refresh(package)
    return RunbookPackageResponse.model_validate(package)


@router.get(
    "",
    dependencies=[Depends(require_orchestrator)],
    response_model=list[RunbookPackageResponse],
)
def list_runbook_packages(
    db: Annotated[Session, Depends(get_db)],
) -> list[RunbookPackageResponse]:
    packages = db.scalars(
        select(RunbookPackage).order_by(RunbookPackage.name, RunbookPackage.version)
    ).all()
    return [RunbookPackageResponse.model_validate(package) for package in packages]


@router.get(
    "/{package_id}",
    dependencies=[Depends(require_orchestrator)],
    response_model=RunbookPackageDetail,
)
def get_runbook_package(
    package_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> RunbookPackageDetail:
    package = db.get(RunbookPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Runbook package not found.")
    promotions = db.scalars(
        select(RunbookPromotion)
        .where(RunbookPromotion.package_id == package.id)
        .order_by(RunbookPromotion.recorded_at, RunbookPromotion.id)
    ).all()
    return RunbookPackageDetail(
        package=RunbookPackageResponse.model_validate(package),
        promotions=[
            RunbookPromotionResponse.model_validate(promotion)
            for promotion in promotions
        ],
    )


@router.post(
    "/{package_id}/promotions",
    dependencies=[Depends(require_orchestrator)],
    response_model=RunbookPromotionResponse,
    status_code=status.HTTP_201_CREATED,
)
def promote_runbook(
    package_id: UUID,
    payload: RunbookPromotionCreate,
    db: Annotated[Session, Depends(get_db)],
) -> RunbookPromotionResponse:
    package = db.get(RunbookPackage, package_id)
    if package is None:
        raise HTTPException(status_code=404, detail="Runbook package not found.")
    promotion = promote_runbook_package(db, package, payload)
    return RunbookPromotionResponse.model_validate(promotion)
