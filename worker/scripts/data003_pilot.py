#!/usr/bin/env python3
"""Exercise DATA-003 governance and recovery against the live DATA-002 catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import httpx


def digest(document) -> str:
    return hashlib.sha256(
        json.dumps(
            document, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()


def call(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/var/lib/invariance-swarm/data003/report.json"),
    )
    args = parser.parse_args()
    with httpx.Client(
        base_url=os.environ["SWARM_API_URL"].rstrip("/"),
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
        timeout=90,
    ) as client:
        catalogs = call(client, "GET", "/v1/research/market-data-catalog/snapshots")
        catalog = next(
            item for item in catalogs if item["catalog_key"] == "DATA002-BINANCE-BTC-R2"
        )
        partition = catalog["catalog"]["partitions"][-1]
        output_digest = hashlib.sha256(b"data003-curated-publication").hexdigest()
        backup_digest = hashlib.sha256(b"data003-verified-backup").hexdigest()
        transformation_digest = hashlib.sha256(b"data003-normalize-bars-v1").hexdigest()
        contract = {
            "schema_version": 1,
            "as_of": "2026-08-27T00:00:00Z",
            "catalog_digest": catalog["catalog_digest"],
            "quality_slos": [
                {
                    "dataset_key": partition["dataset_key"],
                    "layer": partition["layer"],
                    "maximum_freshness_seconds": 31536000,
                    "maximum_duplicate_count": 0,
                    "maximum_gap_count": 0,
                    "expected_schema_digest": partition["schema_digest"],
                }
            ],
            "lineage_edges": [
                {
                    "edge_id": "data003-raw-to-curated-r1",
                    "input_digest": partition["content_digest"],
                    "output_digest": output_digest,
                    "transformation_digest": transformation_digest,
                    "transformation_name": "normalize-bars-v1",
                }
            ],
            "entitlements": [
                {
                    "rule_id": "data003-research-runner-r1",
                    "principal": "research-runner",
                    "dataset_keys": [partition["dataset_key"]],
                    "actions": ["read", "delete"],
                    "purpose": "systematic-research",
                    "valid_from": "2026-01-01T00:00:00Z",
                    "valid_to": None,
                }
            ],
            "storage_budgets": [
                {
                    "budget_key": "data003-binance-budget-r1",
                    "dataset_key": partition["dataset_key"],
                    "maximum_bytes": 1000,
                    "warning_percent": 80,
                }
            ],
            "observed_storage_bytes": {partition["dataset_key"]: 850},
            "retention_holds": [
                {
                    "hold_id": "data003-reproducibility-hold-r1",
                    "object_digest": partition["content_digest"],
                    "reason_code": "research-reproducibility",
                    "active_from": "2026-01-01T00:00:00Z",
                    "active_until": None,
                }
            ],
            "recovery_manifests": [
                {
                    "recovery_key": "data003-backup-r1",
                    "backup_digest": backup_digest,
                    "catalog_digest": catalog["catalog_digest"],
                    "object_digests": [partition["content_digest"]],
                    "created_at": "2026-08-27T00:00:00Z",
                    "integrity_verified": True,
                    "verifier": "data003-pilot",
                }
            ],
            "publications": [
                {
                    "publication_key": "data003-curated-btc-r1",
                    "publication_digest": output_digest,
                    "catalog_digest": catalog["catalog_digest"],
                    "output_digests": [output_digest],
                }
            ],
        }
        snapshot_digest = digest(contract)
        response = client.post(
            "/v1/research/lake-operations/snapshots",
            json={
                "snapshot_key": "DATA003-LAKE-GOVERNANCE-R1",
                "snapshot": contract,
                "snapshot_digest": snapshot_digest,
                "supersedes_snapshot_id": None,
                "registered_by": "data003-pilot",
            },
        )
        if response.status_code == 409:
            snapshots = call(client, "GET", "/v1/research/lake-operations/snapshots")
            snapshot = next(
                item
                for item in snapshots
                if item["snapshot_key"] == "DATA003-LAKE-GOVERNANCE-R1"
            )
            if snapshot["snapshot_digest"] != snapshot_digest:
                raise RuntimeError("Existing DATA-003 fixture has a different digest.")
        else:
            response.raise_for_status()
            snapshot = response.json()

        def admission(**updates):
            payload = {
                "snapshot_digest": snapshot_digest,
                "partition_digest": partition["content_digest"],
                "principal": "research-runner",
                "action": "read",
                "purpose": "systematic-research",
                "evaluated_at": "2026-02-01T00:00:00Z",
                "observed_schema_digest": partition["schema_digest"],
                "duplicate_count": 0,
                "gap_count": 0,
                "last_available_at": partition["available_at"],
            }
            payload.update(updates)
            return call(
                client,
                "POST",
                "/v1/research/lake-operations/admissions",
                json=payload,
            )

        clean = admission()
        corrupt = admission(duplicate_count=1)
        denied = admission(principal="unknown-runner")
        held = admission(action="delete")
        disabled = call(
            client,
            "POST",
            "/v1/research/lake-operations/publications/disable",
            json={
                "snapshot_digest": snapshot_digest,
                "publication_key": "data003-curated-btc-r1",
                "acted_by": "data003-pilot",
                "reason_code": "restore-drill",
            },
        )
        restored = call(
            client,
            "POST",
            "/v1/research/lake-operations/publications/restore",
            json={
                "snapshot_digest": snapshot_digest,
                "publication_key": "data003-curated-btc-r1",
                "recovery_key": "data003-backup-r1",
                "restored_catalog_digest": catalog["catalog_digest"],
                "restored_object_digests": [partition["content_digest"]],
                "acted_by": "data003-pilot",
            },
        )
        events = call(
            client,
            "GET",
            "/v1/research/lake-operations/events",
            params={"snapshot_id": snapshot["id"]},
        )
    checks = {
        "clean_read_allowed": clean["allowed"] is True,
        "capacity_warning_observable": clean["storage_state"] == "warning",
        "corrupt_partition_denied": corrupt["allowed"] is False,
        "unknown_principal_denied": denied["allowed"] is False,
        "retention_hold_blocks_delete": held["allowed"] is False
        and "retention_hold" in held["reason_codes"],
        "publication_disabled": disabled["state"] == "disabled",
        "verified_restore_succeeded": restored["state"] == "restored",
        "append_only_events_visible": len(events) >= 6,
        "protected_payload_absent": all(
            "payload" not in item["detail"] for item in events
        ),
    }
    report = {
        "schema_version": "data003-pilot-report-v1.0.0",
        "success": all(checks.values()),
        "checks": checks,
        "snapshot_id": snapshot["id"],
        "snapshot_digest": snapshot_digest,
        "catalog_digest": catalog["catalog_digest"],
        "partition_digest": partition["content_digest"],
        "backup_digest": backup_digest,
        "event_count": len(events),
        "capital_or_order_authority": False,
        "source_write_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
