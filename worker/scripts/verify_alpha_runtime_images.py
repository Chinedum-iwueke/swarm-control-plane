#!/usr/bin/env python3
"""Read-only verification of all containerized alpha decision producers."""

import json
import subprocess


RUNTIMES = (
    "swarm-api",
    "invariance-swarm-alpha-discovery-director-runtime",
    "invariance-swarm-alpha-campaign-director-runtime",
)


def verify(records: list[dict], expected_image: str) -> dict:
    indexed = {str(item.get("Name", "")).lstrip("/"): item for item in records}
    failures = []
    warnings = []
    runtimes = []
    if not expected_image.startswith("sha256:"):
        failures.append("expected_image_id_invalid")
    for name in RUNTIMES:
        item = indexed.get(name)
        if item is None:
            failures.append(f"{name}:missing")
            continue
        state = item.get("State", {})
        healthy = state.get("Health", {}).get("Status")
        if item.get("Image") != expected_image:
            failures.append(f"{name}:stale_image")
        if state.get("Running") is not True or state.get("Restarting") is True:
            failures.append(f"{name}:not_running")
        if name == "swarm-api" and healthy is not None and healthy != "healthy":
            failures.append(f"{name}:health_{healthy}")
        elif name != "swarm-api" and healthy is not None:
            warnings.append(f"{name}:inherited_api_healthcheck_not_director_readiness")
        runtimes.append({
            "name": name, "image": item.get("Image"),
            "running": state.get("Running") is True, "health": healthy,
        })
    return {
        "schema_version": "alpha-runtime-image-parity-v1",
        "expected_image": expected_image, "runtimes": runtimes,
        "failures": failures, "warnings": warnings, "success": not failures,
        "claim_boundary": "Image parity and API health only; verify director loop progress and VM1 worker freshness separately. Not scientific certification.",
    }


def main() -> int:
    try:
        expected = subprocess.run(
            ["docker", "image", "inspect", "invariance-swarm-api:0.4.0", "--format", "{{.Id}}"],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        result = subprocess.run(
            ["docker", "inspect", *RUNTIMES], check=True,
            capture_output=True, text=True, timeout=30,
        )
        report = verify(json.loads(result.stdout), expected)
    except (subprocess.SubprocessError, OSError, ValueError) as exc:
        # Never print docker inspect payloads: Config.Env may contain credentials.
        report = {"success": False, "error": type(exc).__name__}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
