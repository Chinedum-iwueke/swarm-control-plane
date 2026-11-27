"""Pre-authoring data checkpoints resolved from registered catalogs, not model assertions."""

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_data_catalog import MarketDataResolveRequest
from app.services.graph import digest_document
from app.services.market_data_catalog import (
    resolve_market_data,
    MarketDataUnknown,
    MarketDataConflict,
)
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
    normalized = [
        DataCheckpoint.model_validate(item).model_dump(mode="json")
        for item in checkpoints
    ]
    indexed = {digest_document(item): item for item in normalized}
    declaration = DataPrerequisites(
        schema_version="method-data-prerequisites-v1",
        candidate_digest=contract["candidate_digest"],
        source_commit=contract["base_ref"],
        checkpoints=[indexed[key] for key in sorted(indexed)],
        execution_authority=False,
    ).model_dump(mode="json")
    key = digest_document(declaration)
    result = deepcopy(contract)
    old = result.get("dependencies", {}).get("data_prerequisites")
    if old is not None and old != key:
        raise ValueError(
            "Cannot replace frozen data prerequisites; prepare an explicit successor"
        )
    result.setdefault("dependencies", {})["data_prerequisites"] = key
    catalog = result.setdefault("evidence_catalog", {})
    if key in catalog and catalog[key] != declaration:
        raise ValueError("Data prerequisite evidence identity conflict")
    catalog[key] = declaration
    return result


def _validated_requirements(packet, candidate_digest):
    key = packet.get("dependencies", {}).get("data_prerequisites")
    document = packet.get("evidence", {}).get(key) if isinstance(key, str) else None
    if not isinstance(document, dict) or digest_document(document) != key:
        raise DataPrerequisiteUnavailable(
            "assess_method_data_prerequisites",
            {
                "missing": "reviewed structured data prerequisites",
                "execution_authority": False,
            },
        )
    try:
        requirements = DataPrerequisites.model_validate(document)
    except ValueError as exc:
        raise DataPrerequisiteUnavailable(
            "assess_method_data_prerequisites",
            {
                "missing": "valid structured data prerequisites",
                "evidence_digest": key,
                "execution_authority": False,
            },
        ) from exc
    if (
        requirements.candidate_digest != candidate_digest
        or requirements.source_commit != packet.get("source_commit")
    ):
        raise DataPrerequisiteUnavailable(
            "assess_method_data_prerequisites",
            {
                "missing": "candidate/source-bound data prerequisites",
                "evidence_digest": key,
                "execution_authority": False,
            },
        )
    return key, requirements


def _resolve_checkpoint(db, checkpoint, index, key, dataset_bindings):
    try:
        resolution = resolve_market_data(db, checkpoint)
    except (MarketDataUnknown, ReferenceDataUnknown) as exc:
        raise DataPrerequisiteUnavailable(
            "produce_admitted_method_data",
            {
                "checkpoint_index": index,
                "checkpoint": checkpoint.model_dump(mode="json"),
                "reason": str(exc),
                "data_reason_code": getattr(
                    exc, "reason_code", "reference_data_unknown"
                ),
                "evidence_digest": key,
                "execution_authority": False,
            },
        ) from exc
    except (MarketDataConflict, ReferenceDataConflict) as exc:
        raise DataPrerequisiteUnavailable(
            "assess_method_data_prerequisites",
            {
                "checkpoint_index": index,
                "reason": str(exc),
                "evidence_digest": key,
                "execution_authority": False,
            },
        ) from exc
    resolved = resolution.model_dump(mode="json")
    if not any(
        str(binding.get("catalog_id")) == str(resolved["catalog_id"])
        and binding.get("dataset_key") == checkpoint.dataset_key
        and resolved["partition"]["content_digest"]
        in binding.get("partition_digests", [])
        for binding in dataset_bindings
    ):
        raise DataPrerequisiteUnavailable(
            "assess_method_data_prerequisites",
            {
                "checkpoint_index": index,
                "reason": "checkpoint outside candidate dataset bindings",
                "evidence_digest": key,
                "execution_authority": False,
            },
        )
    return resolved


def require_data_prerequisites(db, packet, candidate_digest, dataset_bindings):
    """Fail closed at the first failed checkpoint; not whole-window certification."""
    key, requirements = _validated_requirements(packet, candidate_digest)
    resolutions = [
        _resolve_checkpoint(db, checkpoint, index, key, dataset_bindings)
        for index, checkpoint in enumerate(requirements.checkpoints)
    ]
    return {
        "requirements_digest": key,
        "resolutions": resolutions,
        "execution_authority": False,
        "scientific_certification": False,
    }


def assess_data_prerequisite_checkpoints(
    db, packet, candidate_digest, dataset_bindings
):
    """Collect bounded checkpoint evidence without granting dispatch authority.

    Only expected data failures are collected. Infrastructure errors still fail the
    request rather than being mislabeled as scientific or data unavailability.
    """
    from app.services.alpha_disposition import disposition_for

    key, requirements = _validated_requirements(packet, candidate_digest)
    assessments, resolutions, failures = [], [], []
    for index, checkpoint in enumerate(requirements.checkpoints):
        item = {
            "checkpoint_index": index,
            "checkpoint": checkpoint.model_dump(mode="json"),
        }
        try:
            resolved = _resolve_checkpoint(db, checkpoint, index, key, dataset_bindings)
        except DataPrerequisiteUnavailable as exc:
            failure = {
                "reason_code": exc.reason_code,
                "detail": exc.detail,
                "disposition": disposition_for(exc.reason_code, exc.detail),
            }
            failures.append(failure)
            item.update(status="blocked", **failure)
        else:
            resolutions.append(resolved)
            item.update(status="resolved", resolution=resolved)
        assessments.append(item)
    report = {
        "requirements_digest": key,
        "candidate_digest": candidate_digest,
        "source_commit": requirements.source_commit,
        "status": "blocked" if failures else "declared_checkpoints_resolved",
        "checkpoint_assessments": assessments,
        "resolutions": resolutions,
        "blocked_checkpoint_count": len(failures),
        "resolved_checkpoint_count": len(resolutions),
        "declaration_completeness_reviewed": False,
        "execution_authority": False,
        "scientific_certification": False,
        "evidence_boundary": {
            "scope": "declared_catalog_checkpoints_only",
            "whole_window_continuity_proven": False,
            "uninterrupted_historical_tradability_proven": False,
            "contemporaneous_basket_membership_proven": False,
            "required_followup": "Independent assessment of all scientific data claims remains required; "
            "resolved checkpoints do not establish these broader claims.",
        },
    }
    if failures:
        # Preserve the existing first-blocker API fields for callers.
        report.update(failures[0])
    return report
