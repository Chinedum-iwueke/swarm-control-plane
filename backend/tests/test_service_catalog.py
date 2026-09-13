from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.schemas.platform import (
    ReconciliationRequest,
    ServiceCatalogCreate,
    ServiceObservation,
)
from app.services.platform import canonical_digest, manifest_document, reconcile_catalog
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]


def catalog() -> ServiceCatalogCreate:
    return ServiceCatalogCreate.model_validate_json(
        (ROOT / "worker/service-catalog/hermes-platform-v1.json").read_text()
    )


def observation(key="control-plane-postgres", version="17", observed_at=None):
    return ServiceObservation(
        service_key=key,
        machine="vm2-deployment",
        runtime_kind="docker",
        status="healthy",
        observed_at=observed_at or datetime(2026, 8, 25, tzinfo=UTC),
        interfaces={"postgres": version},
    )


def test_catalog_is_closed_owned_and_digest_stable():
    value = catalog()
    assert len(value.entries) == 13
    exec1 = next(item for item in value.entries if item.service_key == "fleet-probe-exec1")
    assert exec1.intended_machines == ["exec1-execution"]
    assert exec1.owner == "platform-operations"
    assert canonical_digest(manifest_document(value)) == canonical_digest(
        manifest_document(value)
    )
    raw = value.model_dump(mode="json")
    raw["entries"][0]["owner"] = ""
    with pytest.raises(ValidationError):
        ServiceCatalogCreate.model_validate(raw)


def test_reconciliation_detects_orphan_stale_and_incompatible_interface():
    value = catalog()
    now = datetime(2026, 8, 25, tzinfo=UTC)
    observations = []
    for entry in value.entries:
        versions = {item.name: item.version for item in entry.interfaces}
        observations.append(
            ServiceObservation(
                service_key=entry.service_key,
                machine=entry.intended_machines[0],
                runtime_kind=entry.runtime_kind,
                status="healthy",
                observed_at=now,
                interfaces=versions,
            )
        )
    observations[0] = observation(
        version="16", observed_at=now - timedelta(seconds=301)
    )
    observations.append(
        ServiceObservation(
            service_key="unknown-daemon",
            machine="vm2-deployment",
            runtime_kind="systemd",
            status="healthy",
            observed_at=now,
            interfaces={},
        )
    )
    result = reconcile_catalog(
        manifest_document(value),
        ReconciliationRequest(
            observations=observations, freshness_seconds=300, observed_at=now
        ),
    )
    codes = {item["code"] for item in result["findings"]}
    assert {"orphan_service", "stale_observation", "incompatible_interface"} <= codes
    assert result["status"] == "failed"


def test_reconciliation_passes_and_is_replay_deterministic():
    value = catalog()
    now = datetime(2026, 8, 25, tzinfo=UTC)
    observations = [
        ServiceObservation(
            service_key=e.service_key,
            machine=e.intended_machines[0],
            runtime_kind=e.runtime_kind,
            status="healthy",
            observed_at=now,
            interfaces={i.name: i.version for i in e.interfaces},
        )
        for e in value.entries
    ]
    request = ReconciliationRequest(observations=observations, observed_at=now)
    first = reconcile_catalog(manifest_document(value), request)
    second = reconcile_catalog(manifest_document(value), request)
    assert first["status"] == "passed"
    assert first["report_digest"] == second["report_digest"]
