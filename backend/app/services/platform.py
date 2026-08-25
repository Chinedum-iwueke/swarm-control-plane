import hashlib
import json
from datetime import UTC, datetime

from app.schemas.platform import ReconciliationRequest, ServiceCatalogCreate


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def manifest_document(payload: ServiceCatalogCreate) -> dict:
    return payload.model_dump(mode="json")


def reconcile_catalog(manifest: dict, payload: ReconciliationRequest) -> dict:
    now = payload.observed_at or datetime.now(UTC)
    entries = {item["service_key"]: item for item in manifest["entries"]}
    observations = {item.service_key: item for item in payload.observations}
    findings: list[dict] = []

    for key, observation in sorted(observations.items()):
        entry = entries.get(key)
        if entry is None:
            findings.append(
                {"code": "orphan_service", "service_key": key, "severity": "error"}
            )
            continue
        age = (now - observation.observed_at).total_seconds()
        if age > payload.freshness_seconds:
            findings.append(
                {
                    "code": "stale_observation",
                    "service_key": key,
                    "severity": "error",
                    "age_seconds": round(age, 3),
                }
            )
        if observation.machine not in entry["intended_machines"]:
            findings.append(
                {
                    "code": "wrong_machine",
                    "service_key": key,
                    "severity": "error",
                    "machine": observation.machine,
                }
            )
        if observation.runtime_kind != entry["runtime_kind"]:
            findings.append(
                {"code": "runtime_mismatch", "service_key": key, "severity": "error"}
            )
        if observation.status != "healthy":
            findings.append(
                {
                    "code": "unhealthy_service",
                    "service_key": key,
                    "severity": "error",
                    "status": observation.status,
                }
            )
        expected = {item["name"]: item["version"] for item in entry["interfaces"]}
        for name, version in sorted(expected.items()):
            if observation.interfaces.get(name) != version:
                findings.append(
                    {
                        "code": "incompatible_interface",
                        "service_key": key,
                        "severity": "error",
                        "interface": name,
                        "expected": version,
                        "observed": observation.interfaces.get(name),
                    }
                )

    for key, entry in sorted(entries.items()):
        if key not in observations:
            findings.append(
                {"code": "missing_service", "service_key": key, "severity": "error"}
            )
        for dependency in entry["dependencies"]:
            observed = observations.get(dependency["service_key"])
            if dependency["required"] and (
                observed is None or observed.status != "healthy"
            ):
                findings.append(
                    {
                        "code": "dependency_unavailable",
                        "service_key": key,
                        "dependency": dependency["service_key"],
                        "severity": "error",
                    }
                )

    observations_doc = [item.model_dump(mode="json") for item in payload.observations]
    observations_doc.sort(key=lambda item: (item["service_key"], item["machine"]))
    findings.sort(
        key=lambda item: (
            item["code"],
            item["service_key"],
            item.get("dependency", ""),
            item.get("interface", ""),
        )
    )
    core = {
        "catalog_digest": canonical_digest(manifest),
        "observation_digest": canonical_digest(observations_doc),
        "status": "passed" if not findings else "failed",
        "findings": findings,
    }
    return {
        **core,
        "report_digest": canonical_digest(core),
        "observations": observations_doc,
    }
