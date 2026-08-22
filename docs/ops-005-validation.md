# OPS-005 Validation Record

**Date:** 2026-08-22
**Status:** Complete; deployed and production-observed on VM2

## Implemented

- Atomic custom-format PostgreSQL dump and strict versioned manifest.
- Non-empty, `pg_restore --list`, migration-marker, byte-size, and SHA-256 gates.
- Non-blocking overlap lock, minimum-free-space gate, and partial-file cleanup.
- Two-recent, seven-daily, four-weekly, six-monthly verified-generation retention.
- Hardened persistent daily systemd timer with bounded jitter.
- Private runtime Docker configuration directories compatible with `ProtectHome`.
- Explicit Docker-socket group access with an otherwise empty capability set.
- Weekly network-isolated disposable restore drill with RPO/RTO dossier.
- VM2 fleet freshness, integrity, and latest-failure metrics.
- Six-day warning, seven-day critical, and existing three-sample alert/recovery rules.
- Mission Control backup verification and age display.

## Automated verification

Focused tests cover atomic success, interrupted execution, digest corruption,
retention boundaries, overlapping invocation, isolated restore behavior, opt-in probe
metrics, pre-deadline warning classification, notification hysteresis, and strict
observation schemas. Full worker, backend, and Mission Control results are recorded at
the source commit that closes this document.

## Production evidence

- Verified generation `827e705d9ee1`: 980,858,141 bytes, migration
  `b6f2a9c41d80`, completed `2026-08-22T16:32:04.374483Z`.
- Verified generation `2fa39d5941ac`: 980,850,311 bytes, migration
  `b6f2a9c41d80`, completed `2026-08-22T16:21:30.896857Z`.
- Disposable restore of `2fa39d5941ac`: 77 public tables, RPO 4.584 seconds,
  RTO 326.545 seconds, network isolated, no production database contact.
- Daily backup and weekly restore timers are enabled and scheduled with persistent
  bounded jitter; the VM2 fleet probe is active and publishing.
- Real failed backup attempts opened critical incident generation 1 at
  `2026-08-22T15:47:30Z`. The existing founder outbox recorded exactly one critical
  notification. Three healthy samples recovered the same incident at
  `2026-08-22T16:18:22Z` and recorded exactly one recovery notification.
- Targeted source scanning found no credential, private-key, bearer-token, or agent-token
  material in the OPS-005 implementation or evidence documents.

Encrypted off-host replication remains coordinated with PLAT-007 and is not claimed by
OPS-005. That separate disaster-recovery dependency does not weaken the now-active local
backup, freshness, and restore-verification lifecycle.
