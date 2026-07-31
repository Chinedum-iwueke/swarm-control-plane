# M10 Managed Database Cutover And Runbook Packages

## Purpose

M10 prepares the private managed PostgreSQL deployment used by the public
Invariance Research web application for a controlled production cutover. It also
turns the VM2 Deployment Architect from a PostgreSQL-specific coordinator into a
consumer of strict, versioned runbook packages.

M10 does not make the database public and does not execute the final cutover. The
cutover is a risk-4 operation requiring current rehearsal evidence and an explicit
approval bound to the exact package and plan digests.

## Database Ownership Boundary

`vm2-invariance-postgres` is application infrastructure for the public Invariance
Research product. It is not the Hermes control-plane database and it is not a shared
database for agents.

Hermes may later deploy its own managed PostgreSQL target by reusing the package
models and reviewed broker primitives. That target must have a different:

- target profile and DNS name;
- root directory and Docker project;
- database, owners, and application roles;
- credential set and rotation record;
- client allowlist;
- backup destination and restore drill;
- migration, rollback, and cutover approval.

No credential, schema, storage volume, or approval may be inherited merely because
both targets use PostgreSQL.

## Runbook Package Contract

Runbook packages live in `worker/runbook-packages`. They contain declarations, not
shell commands. A package defines:

- semantic name and version;
- typed production and rehearsal target profiles;
- typed parameters with bounded values;
- fixed operation identity and category;
- task type, risk, and approval requirement;
- mandatory preflight checks and failure-closed behavior;
- required bounded evidence;
- rollback operation, triggers, timeout, and rollback evidence;
- rehearsal target, required evidence, and maximum evidence age.

Unknown fields, unsafe names, path traversal, untyped parameters, broad network
ranges, command fields, mutations without approval, and mutations without rollback
are rejected.

The initial generic package covers reviewed operation contracts for Docker, Redis,
storage, certificates, backups, and service health. A declaration does not itself
grant execution. Each mutating operation still requires an audited fixed broker
primitive before it can be deployed.

## Promotion Lifecycle

Packages progress sequentially:

```text
draft -> rehearsed -> approved -> deployed
```

Every record binds the package name, semantic version, canonical manifest SHA-256,
actor, timestamp, previous record digest, and required evidence digest. `approved`
and `deployed` records also require an approval reference. Changing the manifest
invalidates the chain and requires a new rehearsal.

Lifecycle meaning:

- **draft:** reviewed source exists but has no execution authority.
- **rehearsed:** the exact digest passed the declared parity rehearsal recently.
- **approved:** a human approved that exact digest and evidence for the target.
- **deployed:** the approved package was installed and post-deployment evidence was
  recorded.

## Invariance Cutover Preparation

The `invariance-postgres-cutover` package requires:

1. PostgreSQL and PgBouncer healthy on the private VM2 endpoint.
2. Private DNS `db.invarianceresearch.internal` resolving only through the approved
   private network.
3. A trusted CA chain, hostname-valid server certificate, protected key, and at least
   30 days remaining validity.
4. PgBouncer client TLS with certificate verification.
5. Default-deny client policy with explicit approved egress CIDRs.
6. An approved application migration artifact and data-parity query set.
7. Rehearsed service-scoped credential distribution and rotation.
8. Verified source and destination backups plus a rehearsed rollback within the
   declared recovery window.
9. An explicit unexpired founder approval bound to the final package and plan
   digests.

Staging deployment version `1.4.0` adds these inactive artifacts:

- `compose.client-tls.yaml`;
- `conf/client-allowlist.json`;
- `cutover/application-migration.json`;
- `cutover/credential-rotation.json`;
- `cutover/rollback.json`;
- `cutover/approval.json`.

The existing private-start operation does not load the TLS overlay. This prevents a
placeholder certificate or incomplete client policy from disrupting the currently
healthy private database.

## Credential Distribution And Rotation

Credentials are service-scoped. The public web application receives only the
`invariance_app` connection material through its deployment platform's protected
secret store. Migration tooling uses the owner credential only during an approved
migration job. Workers receive a distinct worker role only when required. PostgreSQL
superuser and PgBouncer administrative credentials remain on VM2.

Rotation uses overlap rather than in-place disclosure:

1. create a replacement role credential through a fixed broker primitive;
2. stage the new application secret without logging it;
3. verify a new TLS connection and application health;
4. switch clients during the approved window;
5. retain the prior credential for the bounded rollback interval;
6. revoke the prior credential after reconciliation;
7. record only timestamps, role names, secret-version identifiers, and evidence
   digests.

Passwords, private keys, connection strings, and secret values never enter tasks,
approvals, Telegram, Mission Control, evidence, or logs.

## Application Migration

The application migration artifact must pin the Invariance Research source commit,
database schema revision, migration command identity, expected duration, maintenance
window, compatibility assumptions, and parity query digest. It must support a dry run
against a restored backup before approval.

The cutover sequence is:

```text
freeze writes -> final source backup -> verify backup -> apply migration
-> parity checks -> rotate application connection -> health checks
-> observe -> reconcile -> close rollback window
```

Failure at migration, parity, TLS, application health, or reconciliation invokes the
declared rollback. The agent cannot improvise a repair inside the cutover.

## Rollback

Rollback restores application traffic to the prior database configuration, verifies
the previous application health, preserves the failed destination and logs for audit,
and runs post-rollback data reconciliation. It does not delete either database or
overwrite the failed evidence.

The rehearsal must measure recovery time and prove that rollback needs no interactive
shell or password transmission. If the rehearsal is older than seven days or any
package, application, Docker, certificate, network, or migration input changes, the
approval is stale.

## Completion Gates

### Source-complete

- package and lifecycle schemas implemented;
- generic VM2 package covers the required operational categories;
- Invariance cutover package includes typed inputs, preflight, rehearsal, evidence,
  rollback, and explicit approval;
- inactive TLS and policy artifacts are digest-bound by deployment metadata;
- unit tests prove traversal, unknown fields, arbitrary parameters, broad CIDRs,
  skipped promotion states, and stale digest reuse fail closed.

### Operationally rehearsed

- deploy source to VM2;
- upgrade the staged configuration without rotating existing credentials;
- provision private DNS and certificate through the approved owner;
- populate the exact application egress allowlist;
- complete migration and credential-rotation artifacts;
- run the disposable parity rehearsal with TLS, migration, rotation, and rollback;
- register its evidence digest and promote the exact package to `rehearsed`.

### Cutover approved

- founder reviews the complete evidence bundle;
- approval binds package digest, plan digest, target, window, and expiry;
- no material input changes after approval.

### Deployed

- approved cutover primitive completes once;
- application, TLS, data parity, backups, and monitoring pass;
- rollback window closes only after reconciliation;
- deployment evidence and resulting state are registered.

## Current Recommendation

M10 source implementation can be promoted to rehearsal. Production cutover remains
**no-go** until real DNS ownership, trusted certificate material, immutable client
egress CIDRs, application migration inputs, credential-store integration, and a
successful rollback rehearsal are present and explicitly approved.
