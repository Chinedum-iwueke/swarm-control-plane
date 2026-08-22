# OPS-005 Validation Record

**Date:** 2026-08-22
**Status:** Source complete; production evidence pending

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

## Production acceptance gate

OPS-005 is not production-complete until VM2 retains two consecutive verified
manifests, one successful disposable restore dossier with measured RPO/RTO, an observed
stale/failure alert and recovery transition, timer/unit verification, and a no-secret
scan. Off-host encrypted replication remains coordinated with PLAT-007 and is not
claimed by this milestone.
