from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "ops003-disaster-recovery-dossier-v1.0.0"


class DisasterRecoveryError(ValueError):
    """Recovery evidence is incomplete, inconsistent, or exceeds policy."""


class RecoveryThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    control_plane_rpo_seconds: float = Field(gt=0)
    control_plane_rto_seconds: float = Field(gt=0)
    corpus_rpo_seconds: float = Field(gt=0)
    corpus_rto_seconds: float = Field(gt=0)
    max_duplicate_executions: int = Field(default=0, ge=0)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _digest(value: object, field: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise DisasterRecoveryError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DisasterRecoveryError(message)


def _reject_secrets(evidence: dict[str, Any]) -> None:
    serialized = json.dumps(evidence, sort_keys=True).lower()
    forbidden = (
        "api_key",
        "api_secret",
        "private_key",
        "password",
        "bearer ",
        "agent_token",
    )
    _require(
        not any(marker in serialized for marker in forbidden),
        "recovery evidence contains credential material",
    )


def build_disaster_recovery_dossier(
    evidence: dict[str, Any],
    thresholds: RecoveryThresholds,
) -> dict[str, Any]:
    """Validate a non-destructive integrated drill and address its evidence."""
    evidence = deepcopy(evidence)
    _reject_secrets(evidence)

    control = evidence.get("control_plane") or {}
    backup = control.get("backup") or {}
    restore = control.get("restore") or {}
    backup_digest = _digest(backup.get("sha256"), "control_plane.backup.sha256")
    _require(backup.get("integrity_verified") is True, "control-plane backup is unverified")
    _require(int(backup.get("byte_size", 0)) > 0, "control-plane backup is empty")
    _require(restore.get("success") is True, "control-plane restore drill failed")
    _require(restore.get("network_isolated") is True, "restore drill was not isolated")
    _require(
        str(restore.get("backup_id")) == str(backup.get("backup_id")),
        "restore drill did not use the declared backup",
    )
    _require(
        str(restore.get("backup_sha256")) == backup_digest,
        "restore drill digest differs from the backup",
    )
    _require(
        restore.get("migration_marker") == backup.get("migration_marker"),
        "restored migration marker differs from the backup",
    )
    _require(int(restore.get("table_count", 0)) > 0, "restored database has no tables")
    _require(
        float(restore.get("rpo_seconds", float("inf")))
        <= thresholds.control_plane_rpo_seconds,
        "control-plane RPO exceeded policy",
    )
    _require(
        float(restore.get("rto_seconds", float("inf")))
        <= thresholds.control_plane_rto_seconds,
        "control-plane RTO exceeded policy",
    )

    corpus = evidence.get("research_intelligence") or {}
    corpus_backup = corpus.get("backup") or {}
    corpus_restore = corpus.get("restore") or {}
    corpus_digest = _digest(
        corpus_backup.get("corpus_digest"),
        "research_intelligence.backup.corpus_digest",
    )
    _digest(
        corpus_backup.get("manifest_digest"),
        "research_intelligence.backup.manifest_digest",
    )
    _require(corpus_restore.get("success") is True, "corpus restore failed")
    _require(
        corpus_restore.get("restored_corpus_digest") == corpus_digest,
        "restored corpus digest differs from its backup",
    )
    _require(
        float(corpus_restore.get("rpo_seconds", float("inf")))
        <= thresholds.corpus_rpo_seconds,
        "corpus RPO exceeded policy",
    )
    _require(
        float(corpus_restore.get("rto_seconds", float("inf")))
        <= thresholds.corpus_rto_seconds,
        "corpus RTO exceeded policy",
    )
    for name in ("retrieval", "graph"):
        projection = (corpus.get("projections") or {}).get(name) or {}
        _digest(projection.get("digest"), f"{name} projection digest")
        _require(projection.get("stale") is False, f"{name} projection is stale")
        _require(
            projection.get("source_corpus_digest") == corpus_digest,
            f"{name} projection was not rebuilt from the restored corpus",
        )
    _require(corpus.get("citation_replay_passed") is True, "citation replay failed")

    workers = evidence.get("workers") or {}
    stale = int(workers.get("stale_leases_detected", -1))
    reclaimed = int(workers.get("stale_leases_reclaimed", -1))
    _require(stale >= 1, "stale-lease recovery was not exercised")
    _require(reclaimed == stale, "not every stale lease was reclaimed")
    _require(workers.get("task_replay_passed") is True, "task replay failed")
    _require(
        int(workers.get("duplicate_executions", -1))
        <= thresholds.max_duplicate_executions,
        "task replay produced duplicate execution",
    )
    _require(workers.get("notification_sent") is True, "recovery notification was absent")
    _require(
        int(workers.get("notification_duplicates", -1)) == 0,
        "recovery notification was duplicated",
    )

    runtime = evidence.get("runtime_replacement") or {}
    _require(
        runtime.get("baseline_runtime") != runtime.get("replacement_runtime"),
        "runtime replacement did not replace a runtime",
    )
    _require(runtime.get("schema_compatible") is True, "replacement schema is incompatible")
    _require(runtime.get("task_replay_passed") is True, "replacement task replay failed")
    _require(runtime.get("fallback_passed") is True, "runtime fallback failed")
    _require(
        _digest(runtime.get("baseline_output_digest"), "baseline output digest")
        == _digest(runtime.get("replacement_output_digest"), "replacement output digest"),
        "replacement changed the canonical task output",
    )

    secrets = evidence.get("secret_rotation") or {}
    _require(
        secrets.get("new_credential_activated") is True,
        "new credential was not activated",
    )
    _require(secrets.get("old_credential_revoked") is True, "old credential was not revoked")
    _require(secrets.get("redaction_verified") is True, "secret redaction was not verified")

    sections = {
        name: canonical_digest(evidence[name])
        for name in (
            "control_plane",
            "research_intelligence",
            "workers",
            "runtime_replacement",
            "secret_rotation",
        )
    }
    dossier: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "production_resources_touched": False,
        "production_restore_authority": False,
        "evidence": evidence,
        "section_digests": sections,
        "thresholds": thresholds.model_dump(mode="json"),
        "checks": {
            "control_plane_restore": True,
            "research_intelligence_restore": True,
            "derived_state_rebuilt": True,
            "stale_lease_recovered_once": True,
            "notification_deduplicated": True,
            "runtime_replaced_and_fallback_replayed": True,
            "secret_rotation_redacted": True,
        },
    }
    dossier["dossier_digest"] = canonical_digest(dossier)
    return dossier


def validate_disaster_recovery_dossier(dossier: dict[str, Any]) -> None:
    if dossier.get("schema_version") != SCHEMA_VERSION:
        raise DisasterRecoveryError("unsupported disaster-recovery dossier schema")
    supplied = _digest(dossier.get("dossier_digest"), "dossier_digest")
    core = {key: value for key, value in dossier.items() if key != "dossier_digest"}
    _require(supplied == canonical_digest(core), "disaster-recovery dossier digest mismatch")
    _require(dossier.get("status") == "passed", "disaster-recovery dossier did not pass")
    _require(
        dossier.get("production_resources_touched") is False,
        "rehearsal touched production resources",
    )
    _require(
        dossier.get("production_restore_authority") is False,
        "rehearsal granted production restore authority",
    )
