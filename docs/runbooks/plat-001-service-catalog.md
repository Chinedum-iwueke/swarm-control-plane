# PLAT-001 Service Catalog Runbook

## Purpose

PLAT-001 records intended service ownership, interfaces, dependencies, data classes, SLOs, and recovery ownership without replacing Docker, systemd, launchd, role deployments, fleet telemetry, or the operation ledger as runtime truth sources.

## Register and activate

1. Validate `worker/service-catalog/hermes-platform-v1.json` with `ServiceCatalogCreate`.
2. `POST /v1/platform/service-catalogs` using the orchestrator credential.
3. Inspect its returned manifest digest and source commit.
4. `POST /v1/platform/service-catalogs/{snapshot_id}/activate` with a specific reason.
5. Submit runtime observations to `POST /v1/platform/service-catalogs/reconcile`.
6. Treat any orphan, missing, stale, unhealthy, wrong-machine, runtime-mismatch, incompatible-interface, or unavailable-dependency finding as a failed reconciliation.

Registration is idempotent by manifest digest. Reusing a semantic catalog version with a different digest is rejected.

## Rollback

Catalog activation never mutates a snapshot. Activate the previously retained snapshot ID. The new activation records the prior snapshot ID and leaves the full history intact. Catalog rollback changes declared intent only; it does not mutate running services.

## Recovery

Use the entry's `recovery_owner` and `recovery_plan` to route recovery. Reconcile again after the runtime operation is visible through its native truth source. Never edit an observation to hide drift.
