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

## Recommendation

**Go** for deploying the registry migration and updated Deployment Architect package,
then rehearsing the standard read-only operations and one controlled restart on VM2.
**No-go** for marking the package approved or deployed until that evidence is
registered. **No-go** for the Invariance PostgreSQL application cutover, certificate
rotation, firewall mutation, or credential rotation under M10B.
