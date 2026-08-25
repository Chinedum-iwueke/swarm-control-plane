#!/usr/bin/env python3
"""Build a deterministic no-production OPS-003 recovery rehearsal dossier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swarm_worker.disaster_recovery import (
    RecoveryThresholds,
    build_disaster_recovery_dossier,
    canonical_digest,
    validate_disaster_recovery_dossier,
)


def fixture() -> dict:
    corpus = canonical_digest({"restored": "canonical-corpus"})
    backup = canonical_digest({"dump": "control-plane"})
    output = canonical_digest({"task": "bounded-replay", "result": "accepted"})
    return {
        "control_plane": {
            "backup": {
                "backup_id": "ops003-control-plane",
                "sha256": backup,
                "byte_size": 980_858_141,
                "migration_marker": "b6f2a9c41d80",
                "integrity_verified": True,
            },
            "restore": {
                "success": True,
                "network_isolated": True,
                "backup_id": "ops003-control-plane",
                "backup_sha256": backup,
                "migration_marker": "b6f2a9c41d80",
                "table_count": 77,
                "rpo_seconds": 4.584,
                "rto_seconds": 326.545,
            },
        },
        "research_intelligence": {
            "backup": {
                "corpus_digest": corpus,
                "manifest_digest": canonical_digest({"manifest": corpus}),
            },
            "restore": {
                "success": True,
                "restored_corpus_digest": corpus,
                "rpo_seconds": 30.0,
                "rto_seconds": 420.0,
            },
            "projections": {
                "retrieval": {
                    "digest": canonical_digest({"retrieval": corpus}),
                    "source_corpus_digest": corpus,
                    "stale": False,
                },
                "graph": {
                    "digest": canonical_digest({"graph": corpus}),
                    "source_corpus_digest": corpus,
                    "stale": False,
                },
            },
            "citation_replay_passed": True,
        },
        "workers": {
            "stale_leases_detected": 1,
            "stale_leases_reclaimed": 1,
            "task_replay_passed": True,
            "duplicate_executions": 0,
            "notification_sent": True,
            "notification_duplicates": 0,
        },
        "runtime_replacement": {
            "baseline_runtime": "fixture-frontier-runtime",
            "replacement_runtime": "fixture-compatible-runtime",
            "schema_compatible": True,
            "baseline_output_digest": output,
            "replacement_output_digest": output,
            "task_replay_passed": True,
            "fallback_passed": True,
        },
        "secret_rotation": {
            "new_credential_activated": True,
            "old_credential_revoked": True,
            "redaction_verified": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dossier = build_disaster_recovery_dossier(
        fixture(),
        RecoveryThresholds(
            control_plane_rpo_seconds=3600,
            control_plane_rto_seconds=900,
            corpus_rpo_seconds=86400,
            corpus_rto_seconds=1800,
        ),
    )
    validate_disaster_recovery_dossier(dossier)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.write_text(json.dumps(dossier, indent=2, sort_keys=True) + "\n")
    args.output.chmod(0o600)
    print(json.dumps(dossier, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
