# M5/M6 Infrastructure Validation

Date: 2026-07-30

## Source Controls

- strict infrastructure contracts with unknown fields forbidden;
- reviewed runbook identity, version, operation, target, risk, and evidence;
- no runbook command arrays or shell strings;
- API-signed tickets bound to lease ownership and exact plan digest;
- risk-3 ticket issuance requires consumed, unexpired approval;
- deterministic nonce and root-side replay ledger;
- unprivileged worker without Docker socket or `sudo`;
- root broker with fixed argument-array operations;
- complete evidence stored locally and registered by digest;
- bounded API result;
- pre/post restart verification and exact rollback;
- no application-source writes, remote Git operations, or arbitrary repair.

## Automated Evidence

- backend suite: 20 passed;
- worker suite: 116 passed;
- broker signature, expiry, replay, root, command-array, timeout, backup
  integrity, bounded recovery, and rollback tests passed;
- runbook unknown-field and arbitrary-parameter tests passed;
- API client lease-token redaction test passed;
- worker Ruff and compileall passed;
- changed-backend Ruff and backend compileall passed;
- installation scripts passed `bash -n`;
- unit verification remains an operational VM2 gate because the declared VM2
  executable and writable paths do not exist on VM1.

Repository-wide backend Ruff also reports ten pre-existing import-order and
broad health-boundary findings outside the M5/M6 changed scope. The M5/M6
backend files are clean; the older findings remain existing maintenance debt.

## Operational Evidence

### Deployment

- control-plane API image: `invariance-swarm-api:0.4.0`;
- API, PostgreSQL, and Redis healthy after deployment;
- dedicated agent: `vm2-infrastructure-operator`;
- root broker active with the unprivileged infrastructure worker disabled;
- broker operations use a private Docker configuration directory inside the
  hardened service mount namespace;
- backup read access is limited to the broker through a dedicated reader group.

### M5 Observation

- task: `4155165e-4304-4a82-9603-173b7aad43a5`;
- task number: `VM2-OBSERVE-20260730T114801071035Z`;
- outcome: succeeded on attempt 1;
- executing agent: `vm2-infrastructure-operator`;
- events: `task_created`, `task_leased`, `task_started`,
  `broker_ticket_issued`, `task_heartbeat`, `task_completed`;
- Docker, PostgreSQL, Redis, API, storage, and backup evidence collected
  without mutation;
- latest backup integrity check returned 0 and `integrity_ok=true`;
- evidence artifact size: 5,996 bytes;
- evidence SHA-256:
  `7ecdbebfa05de21e85510b1a08be63bfccaa1478ba0d253efb69c26ab67a3269`;
- the task result digest matched the artifact registry digest.

### M6 Controlled Restart

- task: `05ad54b9-f3d5-4c00-977c-07e355f6cfa9`;
- task number: `VM2-RESTART-20260730T115015284030Z`;
- approval: `ff5a9ff0-b5a2-4e6d-9602-4e1296d96640`;
- plan digest:
  `bc50ba1014ff33e68defbba9a1c727e2513d782fa1473547834d62cba1c16879`;
- approval events: `approval_requested`, `approval_granted`,
  `approval_consumed`;
- approval was consumed once at lease by the control plane;
- outcome: succeeded on attempt 1;
- executing agent: `vm2-infrastructure-operator`;
- task events: `task_created`, `task_leased`, `task_started`,
  `broker_ticket_issued`, `task_heartbeat`, `task_completed`;
- pre-restart and post-restart health checks passed;
- the fixed API-only restart returned 0;
- rollback was not required or attempted;
- evidence artifact size: 11,875 bytes;
- evidence SHA-256:
  `762432a86e1ee091d283068479ca934efcf64050116a295ac77ec2ee95698be9`;
- the task result digest matched the artifact registry digest;
- API image `invariance-swarm-api:0.4.0` was healthy after restart.

### Preflight Findings

The supervised rollout found and corrected five fail-closed deployment
compatibility issues before the successful pilots: API secret mount
permissions, PostgreSQL backup-tool version mismatch, Python 3.10 datetime
compatibility, broker backup read permissions, and Docker Compose discovery
under `ProtectHome=true`. Failed attempts did not perform an infrastructure
mutation or report stale completion.

## Recommendation

M5 and M6 are operationally complete. The read-only observer and one
approval-gated API restart are validated for their current narrow contracts.
The continuous infrastructure worker remains disabled and inactive. Enabling
continuous leasing should be a separate operator decision after an observation
soak period and alerting are in place.

The successful M6 pilot did not exercise rollback. A rollback drill remains a
future disposable-environment test and must not be induced against production
solely for validation.
