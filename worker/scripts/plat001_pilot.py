#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.platform import (
    ReconciliationRequest,
    ServiceCatalogCreate,
    ServiceObservation,
)
from app.services.platform import (
    canonical_digest,
    manifest_document,
    reconcile_catalog,
)


def observations(
    catalog: ServiceCatalogCreate, now: datetime
) -> list[ServiceObservation]:
    return [
        ServiceObservation(
            service_key=entry.service_key,
            machine=entry.intended_machines[0],
            runtime_kind=entry.runtime_kind,
            status="healthy",
            observed_at=now,
            interfaces={item.name: item.version for item in entry.interfaces},
        )
        for entry in catalog.entries
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the deterministic PLAT-001 reconciliation pilot."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = ServiceCatalogCreate.model_validate_json(
        (ROOT / "worker/service-catalog/hermes-platform-v1.json").read_text()
    )
    now = datetime(2026, 8, 25, 12, tzinfo=UTC)
    clean = observations(catalog, now)
    passing = reconcile_catalog(
        manifest_document(catalog),
        ReconciliationRequest(observations=clean, observed_at=now),
    )
    adversarial = list(clean)
    adversarial[0] = adversarial[0].model_copy(
        update={
            "observed_at": now - timedelta(seconds=301),
            "interfaces": {"postgres": "16"},
        }
    )
    adversarial.append(
        ServiceObservation(
            service_key="orphan-daemon",
            machine="vm2-deployment",
            runtime_kind="systemd",
            status="healthy",
            observed_at=now,
            interfaces={},
        )
    )
    failing = reconcile_catalog(
        manifest_document(catalog),
        ReconciliationRequest(observations=adversarial, observed_at=now),
    )
    report = {
        "schema_version": "plat001-validation-v1.0.0",
        "catalog_version": catalog.catalog_version,
        "catalog_digest": canonical_digest(manifest_document(catalog)),
        "service_count": len(catalog.entries),
        "clean_reconciliation": {
            key: value for key, value in passing.items() if key != "observations"
        },
        "adversarial_reconciliation": {
            key: value for key, value in failing.items() if key != "observations"
        },
        "rollback_contract": "activate any retained prior immutable snapshot",
        "success": passing["status"] == "passed"
        and {"orphan_service", "stale_observation", "incompatible_interface"}
        <= {item["code"] for item in failing["findings"]},
    }
    report["report_digest"] = canonical_digest(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
