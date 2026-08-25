from __future__ import annotations

from copy import deepcopy

import pytest

from swarm_worker.disaster_recovery import (
    DisasterRecoveryError,
    RecoveryThresholds,
    build_disaster_recovery_dossier,
    canonical_digest,
    validate_disaster_recovery_dossier,
)


def thresholds() -> RecoveryThresholds:
    return RecoveryThresholds(
        control_plane_rpo_seconds=3600,
        control_plane_rto_seconds=900,
        corpus_rpo_seconds=86400,
        corpus_rto_seconds=1800,
    )


def evidence() -> dict:
    corpus = "c" * 64
    backup = "a" * 64
    output = canonical_digest({"result": "same canonical task"})
    return {
        "control_plane": {
            "backup": {
                "backup_id": "backup-1",
                "sha256": backup,
                "byte_size": 1024,
                "migration_marker": "head-1",
                "integrity_verified": True,
            },
            "restore": {
                "success": True,
                "network_isolated": True,
                "backup_id": "backup-1",
                "backup_sha256": backup,
                "migration_marker": "head-1",
                "table_count": 77,
                "rpo_seconds": 60.0,
                "rto_seconds": 120.0,
            },
        },
        "research_intelligence": {
            "backup": {"corpus_digest": corpus, "manifest_digest": "b" * 64},
            "restore": {
                "success": True,
                "restored_corpus_digest": corpus,
                "rpo_seconds": 120.0,
                "rto_seconds": 240.0,
            },
            "projections": {
                "retrieval": {
                    "digest": "d" * 64,
                    "source_corpus_digest": corpus,
                    "stale": False,
                },
                "graph": {
                    "digest": "e" * 64,
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
            "baseline_runtime": "frontier-runtime-a",
            "replacement_runtime": "compatible-runtime-b",
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


def test_dossier_is_deterministic_non_destructive_and_valid() -> None:
    first = build_disaster_recovery_dossier(evidence(), thresholds())
    second = build_disaster_recovery_dossier(evidence(), thresholds())
    assert first == second
    assert first["production_resources_touched"] is False
    assert first["production_restore_authority"] is False
    validate_disaster_recovery_dossier(first)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("control_plane", "restore", "network_isolated"), False, "not isolated"),
        (("control_plane", "restore", "rto_seconds"), 901, "RTO exceeded"),
        (
            ("research_intelligence", "restore", "restored_corpus_digest"),
            "f" * 64,
            "corpus digest differs",
        ),
        (
            ("research_intelligence", "projections", "graph", "stale"),
            True,
            "graph projection is stale",
        ),
        (("workers", "stale_leases_reclaimed"), 0, "not every stale lease"),
        (("workers", "duplicate_executions"), 1, "duplicate execution"),
        (
            ("runtime_replacement", "replacement_output_digest"),
            "9" * 64,
            "changed the canonical task output",
        ),
        (("runtime_replacement", "fallback_passed"), False, "fallback failed"),
        (("secret_rotation", "old_credential_revoked"), False, "not revoked"),
    ],
)
def test_recovery_failures_are_rejected(
    path: tuple[str, ...], value: object, message: str
) -> None:
    changed = deepcopy(evidence())
    cursor = changed
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    with pytest.raises(DisasterRecoveryError, match=message):
        build_disaster_recovery_dossier(changed, thresholds())


def test_credentials_are_rejected_from_evidence() -> None:
    changed = evidence()
    changed["secret_rotation"]["api_key"] = "must-not-appear"
    with pytest.raises(DisasterRecoveryError, match="credential material"):
        build_disaster_recovery_dossier(changed, thresholds())


def test_tampered_dossier_fails_validation() -> None:
    dossier = build_disaster_recovery_dossier(evidence(), thresholds())
    dossier["checks"]["citation_replay"] = False
    with pytest.raises(DisasterRecoveryError, match="digest mismatch"):
        validate_disaster_recovery_dossier(dossier)
