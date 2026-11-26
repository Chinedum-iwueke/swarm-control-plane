"""Pre-authoring data checkpoints resolved from registered catalogs, not model assertions."""
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_data_catalog import MarketDataResolveRequest
from app.services.graph import digest_document
from app.services.market_data_catalog import resolve_market_data, MarketDataUnknown, MarketDataConflict
from app.services.reference_data import ReferenceDataUnknown, ReferenceDataConflict


class DataCheckpoint(MarketDataResolveRequest):
    catalog_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class DataPrerequisites(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["method-data-prerequisites-v1"]
    candidate_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    checkpoints: list[DataCheckpoint] = Field(min_length=1, max_length=256)
    execution_authority: Literal[False]


class DataPrerequisiteUnavailable(ValueError):
    def __init__(self, reason_code, detail):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.detail = detail


def bind_data_prerequisites(contract, checkpoints):
    """Compile a prospective declaration, never edit an approved record in place.

    Callers must independently review checkpoint completeness and obtain authority
    for the resulting changed contract. This grants no data or execution rights.
    """
    normalized = [DataCheckpoint.model_validate(item).model_dump(mode="json") for item in checkpoints]
    indexed = {digest_document(item): item for item in normalized}
    declaration = DataPrerequisites(schema_version="method-data-prerequisites-v1",
        candidate_digest=contract['candidate_digest'], source_commit=contract['base_ref'],
        checkpoints=[indexed[key] for key in sorted(indexed)], execution_authority=False).model_dump(mode="json")
    key = digest_document(declaration)
    result = deepcopy(contract)
    old = result.get('dependencies', {}).get('data_prerequisites')
    if old is not None and old != key:
        raise ValueError('Cannot replace frozen data prerequisites; prepare an explicit successor')
    result.setdefault('dependencies', {})['data_prerequisites'] = key
    catalog = result.setdefault('evidence_catalog', {})
    if key in catalog and catalog[key] != declaration:
        raise ValueError('Data prerequisite evidence identity conflict')
    catalog[key] = declaration
    return result


def require_data_prerequisites(db, packet, candidate_digest, dataset_bindings):
    """Check only reviewed checkpoints; this is not whole-window certification."""
    key = packet.get("dependencies", {}).get("data_prerequisites")
    document = packet.get("evidence", {}).get(key) if isinstance(key, str) else None
    if not isinstance(document, dict) or digest_document(document) != key:
        raise DataPrerequisiteUnavailable("assess_method_data_prerequisites", {
            "missing": "reviewed structured data prerequisites", "execution_authority": False})
    try:
        requirements = DataPrerequisites.model_validate(document)
    except ValueError as exc:
        raise DataPrerequisiteUnavailable("assess_method_data_prerequisites", {
            "missing": "valid structured data prerequisites", "evidence_digest": key,
            "execution_authority": False}) from exc
    if (requirements.candidate_digest != candidate_digest
            or requirements.source_commit != packet.get("source_commit")):
        raise DataPrerequisiteUnavailable("assess_method_data_prerequisites", {
            "missing": "candidate/source-bound data prerequisites", "evidence_digest": key,
            "execution_authority": False})
    resolutions = []
    for index, checkpoint in enumerate(requirements.checkpoints):
        try:
            resolution = resolve_market_data(db, checkpoint)
        except (MarketDataUnknown, ReferenceDataUnknown) as exc:
            raise DataPrerequisiteUnavailable("produce_admitted_method_data", {
                "checkpoint_index": index, "checkpoint": checkpoint.model_dump(mode="json"),
                "reason": str(exc),
                "data_reason_code": getattr(exc, "reason_code", "reference_data_unknown"),
                "evidence_digest": key, "execution_authority": False}) from exc
        except (MarketDataConflict, ReferenceDataConflict) as exc:
            raise DataPrerequisiteUnavailable("assess_method_data_prerequisites", {
                "checkpoint_index": index, "reason": str(exc), "evidence_digest": key,
                "execution_authority": False}) from exc
        resolved = resolution.model_dump(mode="json")
        if not any(
            str(binding.get('catalog_id')) == str(resolved['catalog_id'])
            and binding.get('dataset_key') == checkpoint.dataset_key
            and resolved['partition']['content_digest'] in binding.get('partition_digests', [])
            for binding in dataset_bindings
        ):
            raise DataPrerequisiteUnavailable("assess_method_data_prerequisites", {
                "checkpoint_index": index, "reason": "checkpoint outside candidate dataset bindings",
                "evidence_digest": key, "execution_authority": False})
        resolutions.append(resolved)
    return {"requirements_digest": key, "resolutions": resolutions,
            "execution_authority": False, "scientific_certification": False}
