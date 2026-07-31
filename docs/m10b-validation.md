# M10B Generalized Deployment Architect Validation

## Scope

M10B turns reviewed infrastructure declarations into a durable, independently
enforced runbook-package system. It does not authorize the Invariance Research
database cutover.

## Trust Chain

```text
signed manifest
  -> control-plane registry
  -> sequential promotion evidence
  -> approved/deployed digest
  -> task plan and typed parameters
  -> signed one-use broker ticket
  -> worker-local role and package verification
  -> broker-local package verification
  -> fixed compiled primitive
  -> bounded evidence and rollback result
```

The API, unprivileged worker, and privileged broker validate the package
independently. A task cannot supply a command, executable, compose path, container
name, certificate path, or rollback command.

## Durable Registry

Migration `9f3b2e7d4a10` creates:

- `runbook_packages`, unique by name/version and canonical digest;
- `runbook_promotions`, append-only and unique by package/state and record digest.

Promotion is strictly `draft -> rehearsed -> approved -> deployed`. Every promoted
state requires evidence; approved and deployed states require an approval reference;
each record contains the prior record digest. A changed manifest is a new digest and
cannot inherit the previous chain.

## Standard Package

`vm2-platform-operations` version `1.0.0` defines:

- Docker service verification;
- Docker Compose service restart with fixed recreate rollback;
- Redis verification;
- storage verification;
- certificate verification;
- backup verification;
- general service-health verification.

Allowed services are fixed to `api`, `postgres`, `pgbouncer`, and `redis`. The broker
maps these logical names to reviewed local containers, Compose services, and project
directories. Certificate verification is restricted to the staged Invariance
PostgreSQL client-TLS profile. Certificate rotation remains outside M10B.

## Safety Results

- package schemas reject unknown fields and command surfaces;
- typed parameters reject missing, unknown, unsafe, non-allowlisted, and overly broad
  network values;
- role-package attestation includes both runbook package file digests;
- broker tickets require a registered package in approved or deployed state;
- task type, risk, target, operation, parameters, package version, and digest must all
  match the registered manifest;
- the broker rejects a mismatching local digest even if a ticket signature is valid;
- mutating package operations require approval and rollback definitions;
- generic restart uses argument arrays, bounded timeouts, post-health verification,
  diagnostics, and a fixed rollback command;
- secrets and arbitrary paths are absent from package and ticket contracts.

## Operational Promotion

The operator CLI is `worker/scripts/runbook_registry.py`. Registration and promotion
require the protected orchestrator environment. Registration additionally requires
the package-signing secret. Rehearsal, approval, and deployment must use real evidence
digests; placeholder evidence is prohibited.

The VM2 parity harness is `worker/scripts/rehearse-platform-runbook.sh`. It creates a
marked disposable Compose project and maps the package's four logical service names
only to rehearsal containers. It exercises every read-only primitive, a successful
controlled restart, and a forced post-check failure that must invoke the broker's real
fixed recreate rollback. The report records the canonical manifest digest, raw package
artifact digest, source commit, VM2 runtime versions, sandbox controls, per-operation
result digests, and rollback result digest.

Run on VM2 only after the exact source commit is deployed:

```bash
cd /srv/invariance/swarm/repositories/swarm-control-plane
sudo worker/scripts/rehearse-platform-runbook.sh run
```

The report is retained at
`/var/lib/invariance-swarm-platform-rehearsal/report.json`. The harness does not call
the registry or change package promotion state. Preserve and inspect the report before
cleanup:

```bash
sudo worker/scripts/rehearse-platform-runbook.sh cleanup
```

## Recommendation

**Go** for deploying the registry migration and updated Deployment Architect package,
then rehearsing the standard read-only operations and one controlled restart on VM2.
**No-go** for marking the package approved or deployed until that evidence is
registered. **No-go** for the Invariance PostgreSQL application cutover, certificate
rotation, firewall mutation, or credential rotation under M10B.

## VM2 Parity Rehearsal Result

The exact `vm2-platform-operations` `1.0.0` package passed its final disposable VM2
parity rehearsal on 2026-07-31.

- source commit: `7b659783da5394b540af771ea668201594f34bba`;
- canonical manifest digest:
  `2a9feadcc1afd80375cfcaf0e060d306ccb36fd2c667fa9d86daa491577bc005`;
- raw package artifact digest:
  `b3d581aaaeb54b4b4630cec05807c7da089366d7592fda1082ca1256fe46538b`;
- evidence report digest:
  `6f1533cf8a8df955122f4f6a843bd232b3fb13e8c026246a383106e79bac50e7`;
- evidence location:
  `/var/lib/invariance-swarm-platform-rehearsal/report.json` on VM2;
- environment: Docker `29.5.2`, Compose `5.1.4`, Python `3.10.12`, Linux
  `5.15.0-185-generic`;
- result: all nine declared read-only primitive checks passed, controlled restarts
  passed for `api`, `postgres`, `pgbouncer`, and `redis`, and the forced unhealthy
  API post-check invoked the fixed recreate rollback and restored a healthy service;
- production verification: `swarm-api`, `swarm-postgres`, and `swarm-redis` remained
  healthy; only `hermes-platform-rehearsal-*` containers were addressed;
- registry verification: the exact package digest remained in `draft` after the run.

The earlier API-only report at source commit `3f10b483c02eb382c9a758334c46ea72b23e70a0`
is superseded because it exposed an environment-file and mutation-coverage gap. The
final report proves the corrected environment handling across every allowlisted
mutation target. The package remained `draft` after rehearsal. This final evidence
qualifies it for a separate explicit promotion to `rehearsed`; approval and deployment
remain later decisions.
