from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import require_orchestrator
from app.db.session import get_db
from app.models.platform import (
    ServiceCatalogActivation,
    ServiceCatalogReconciliation,
    ServiceCatalogSnapshot,
)
from app.schemas.platform import (
    CatalogActivationRequest,
    ReconciliationRequest,
    ServiceCatalogCreate,
    ServiceCatalogResponse,
)
from app.services.platform import canonical_digest, manifest_document, reconcile_catalog

router = APIRouter(
    prefix="/v1/platform",
    tags=["platform"],
    dependencies=[Depends(require_orchestrator)],
)


@router.post("/service-catalogs", response_model=ServiceCatalogResponse)
def register_catalog(
    payload: ServiceCatalogCreate, db: Annotated[Session, Depends(get_db)]
):
    manifest = manifest_document(payload)
    digest = canonical_digest(manifest)
    existing = db.scalar(
        select(ServiceCatalogSnapshot).where(
            ServiceCatalogSnapshot.manifest_digest == digest
        )
    )
    if existing is not None:
        return existing
    version = db.scalar(
        select(ServiceCatalogSnapshot).where(
            ServiceCatalogSnapshot.catalog_version == payload.catalog_version
        )
    )
    if version is not None:
        raise HTTPException(
            status_code=409, detail="Catalog version already has a different digest."
        )
    snapshot = ServiceCatalogSnapshot(
        catalog_version=payload.catalog_version,
        manifest_digest=digest,
        manifest=manifest,
        source_repository=payload.source_repository,
        source_commit=payload.source_commit,
        created_by="founder-operator",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/service-catalogs/active", response_model=ServiceCatalogResponse)
def active_catalog(db: Annotated[Session, Depends(get_db)]):
    activation = db.scalar(
        select(ServiceCatalogActivation)
        .where(ServiceCatalogActivation.is_current.is_(True))
        .order_by(ServiceCatalogActivation.activated_at.desc())
    )
    if activation is None:
        raise HTTPException(status_code=404, detail="No active service catalog.")
    return db.get(ServiceCatalogSnapshot, activation.snapshot_id)


@router.post("/service-catalogs/{snapshot_id}/activate")
def activate_catalog(
    snapshot_id: UUID,
    payload: CatalogActivationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    snapshot = db.get(ServiceCatalogSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Service catalog not found.")
    current = db.scalar(
        select(ServiceCatalogActivation).where(
            ServiceCatalogActivation.is_current.is_(True)
        )
    )
    if current is not None and current.snapshot_id == snapshot_id:
        return {
            "snapshot_id": snapshot_id,
            "manifest_digest": snapshot.manifest_digest,
            "changed": False,
        }
    prior_id = current.snapshot_id if current else None
    db.execute(
        update(ServiceCatalogActivation)
        .where(ServiceCatalogActivation.is_current.is_(True))
        .values(is_current=False)
    )
    db.add(
        ServiceCatalogActivation(
            snapshot_id=snapshot_id,
            prior_snapshot_id=prior_id,
            activated_by="founder-operator",
            reason=payload.reason,
            is_current=True,
        )
    )
    db.commit()
    return {
        "snapshot_id": snapshot_id,
        "manifest_digest": snapshot.manifest_digest,
        "prior_snapshot_id": prior_id,
        "changed": True,
    }


@router.post("/service-catalogs/reconcile")
def reconcile(payload: ReconciliationRequest, db: Annotated[Session, Depends(get_db)]):
    activation = db.scalar(
        select(ServiceCatalogActivation).where(
            ServiceCatalogActivation.is_current.is_(True)
        )
    )
    if activation is None:
        raise HTTPException(
            status_code=409, detail="Activate a service catalog before reconciliation."
        )
    snapshot = db.get(ServiceCatalogSnapshot, activation.snapshot_id)
    report = reconcile_catalog(snapshot.manifest, payload)
    existing = db.scalar(
        select(ServiceCatalogReconciliation).where(
            ServiceCatalogReconciliation.report_digest == report["report_digest"]
        )
    )
    if existing is None:
        db.add(
            ServiceCatalogReconciliation(
                snapshot_id=snapshot.id,
                status=report["status"],
                observations={"items": report["observations"]},
                findings={"items": report["findings"]},
                observation_digest=report["observation_digest"],
                report_digest=report["report_digest"],
            )
        )
        db.commit()
    return {key: value for key, value in report.items() if key != "observations"}


@router.get("/service-catalogs/reconciliations/latest")
def latest_reconciliation(db: Annotated[Session, Depends(get_db)]):
    value = db.scalar(
        select(ServiceCatalogReconciliation)
        .order_by(ServiceCatalogReconciliation.reconciled_at.desc())
        .limit(1)
    )
    if value is None:
        raise HTTPException(
            status_code=404, detail="No service-catalog reconciliation exists."
        )
    return {
        "id": value.id,
        "snapshot_id": value.snapshot_id,
        "status": value.status,
        "findings": value.findings["items"],
        "observation_digest": value.observation_digest,
        "report_digest": value.report_digest,
        "reconciled_at": value.reconciled_at,
    }
