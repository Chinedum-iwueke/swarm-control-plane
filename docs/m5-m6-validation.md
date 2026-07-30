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

Pending reviewed source deployment, agent/package registration, one M5
observation, and one explicitly approved M6 API restart.
