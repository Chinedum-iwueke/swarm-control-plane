from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.data_contract import ResearchDatasetBuild, ResearchDatasetManifest
from app.schemas.data_contract import DatasetBuildCreate, DatasetManifestCreate
from app.services.research import record_digest


class DataContractConflict(ValueError):
    """An immutable dataset key was reused with different content."""


def register_manifest(
    db: Session, payload: DatasetManifestCreate
) -> ResearchDatasetManifest:
    actual = record_digest(payload.manifest)
    if actual != payload.manifest_digest:
        raise DataContractConflict("Dataset manifest digest does not match content.")
    existing = db.scalar(
        select(ResearchDatasetManifest).where(
            or_(
                ResearchDatasetManifest.manifest_key == payload.manifest_key,
                ResearchDatasetManifest.manifest_digest == payload.manifest_digest,
            )
        )
    )
    if existing is not None:
        if existing.manifest_digest == payload.manifest_digest:
            return existing
        raise DataContractConflict("Dataset manifest key already exists.")
    record = ResearchDatasetManifest(
        manifest_key=payload.manifest_key,
        manifest=payload.manifest.model_dump(mode="json"),
        manifest_digest=payload.manifest_digest,
        registered_by=payload.registered_by,
    )
    db.add(record)
    db.flush()
    return record


def register_build(db: Session, payload: DatasetBuildCreate) -> ResearchDatasetBuild:
    manifest = db.get(ResearchDatasetManifest, payload.manifest_id)
    if manifest is None:
        raise LookupError("Dataset manifest not found.")
    document = payload.model_dump(mode="json", exclude={"record_digest", "built_by"})
    actual = record_digest(document)
    if actual != payload.record_digest:
        raise DataContractConflict("Dataset build digest does not match content.")
    existing = db.scalar(
        select(ResearchDatasetBuild).where(
            or_(
                ResearchDatasetBuild.build_key == payload.build_key,
                ResearchDatasetBuild.record_digest == payload.record_digest,
            )
        )
    )
    if existing is not None:
        if existing.record_digest == payload.record_digest:
            return existing
        raise DataContractConflict("Dataset build key already exists.")
    record = ResearchDatasetBuild(**payload.model_dump(mode="python"))
    db.add(record)
    db.flush()
    return record
