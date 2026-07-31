import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RunbookPackage, RunbookPromotion
from app.schemas.runbook_package import (
    RunbookPackageCreate,
    RunbookPackageManifest,
    RunbookPromotionCreate,
)

_STATES = ("draft", "rehearsed", "approved", "deployed")


def canonical_manifest(manifest: RunbookPackageManifest | dict) -> bytes:
    document = (
        manifest.model_dump(mode="json")
        if isinstance(manifest, RunbookPackageManifest)
        else manifest
    )
    return json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()


def verify_runbook_package(payload: RunbookPackageCreate, secret: str) -> None:
    document = canonical_manifest(payload.manifest)
    digest = hashlib.sha256(document).hexdigest()
    signature = hmac.new(secret.encode(), document, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, payload.manifest_digest):
        raise HTTPException(status_code=422, detail="Runbook manifest digest mismatch.")
    if not hmac.compare_digest(signature, payload.signature):
        raise HTTPException(status_code=422, detail="Runbook signature is invalid.")


def promotion_record_digest(document: dict) -> str:
    canonical = json.dumps(
        document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def promote_runbook_package(
    db: Session,
    package: RunbookPackage,
    payload: RunbookPromotionCreate,
    *,
    now: datetime | None = None,
) -> RunbookPromotion:
    promotions = db.scalars(
        select(RunbookPromotion)
        .where(RunbookPromotion.package_id == package.id)
        .order_by(RunbookPromotion.recorded_at, RunbookPromotion.id)
    ).all()
    if [promotion.state for promotion in promotions] != list(
        _STATES[: len(promotions)]
    ):
        raise HTTPException(status_code=409, detail="Promotion chain is invalid.")
    expected = _STATES[len(promotions)] if len(promotions) < len(_STATES) else None
    if payload.state != expected:
        raise HTTPException(status_code=409, detail="Promotion must be sequential.")
    if payload.state != "draft" and payload.evidence_digest is None:
        raise HTTPException(status_code=422, detail="Promotion evidence is required.")
    if payload.state in {"approved", "deployed"} and not payload.approval_reference:
        raise HTTPException(status_code=422, detail="Approval reference is required.")
    previous = promotions[-1] if promotions else None
    recorded_at = now or datetime.now(UTC)
    document = {
        "package_id": str(package.id),
        "manifest_digest": package.manifest_digest,
        "state": payload.state,
        "evidence_digest": payload.evidence_digest,
        "approval_reference": payload.approval_reference,
        "previous_record_digest": previous.record_digest if previous else None,
        "recorded_by": payload.recorded_by,
        "recorded_at": recorded_at.isoformat(),
    }
    promotion = RunbookPromotion(
        package_id=package.id,
        state=payload.state,
        evidence_digest=payload.evidence_digest,
        approval_reference=payload.approval_reference,
        previous_record_digest=previous.record_digest if previous else None,
        record_digest=promotion_record_digest(document),
        recorded_by=payload.recorded_by,
        recorded_at=recorded_at,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return promotion
