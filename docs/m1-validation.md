# M1 Continuous Control and Visibility Validation

Date: 2026-07-30

Branch: `feat/restricted-vm1-worker`

## Source Validation

- backend tests: 3 passed;
- worker tests: 90 passed;
- worker Ruff: passed;
- M1 backend Ruff scope: passed;
- worker compileall: passed;
- shell syntax checks: passed;
- systemd unit verification: passed;
- Alembic graph: one head, `d3f1a8c9b420`;
- Git whitespace validation: passed.

The existing broad backend Ruff baseline still contains findings in modules
outside the M1 change set. M1 files pass the same Ruff executable.

## Controls Verified

- orchestrator-authenticated global, machine, and agent pause/resume;
- append-only control-event persistence;
- pause enforcement before task selection;
- clean paused-worker outcome without workspace preparation;
- no automatic revocation of an already active lease;
- authenticated Prometheus metrics for tasks, agents, leases, versions, and
  pause state;
- worker version in heartbeat metadata and terminal task results;
- conservative, API-confirmed terminal-workspace cleanup with dry-run default;
- custom-format PostgreSQL backup with `PGPASSFILE`, digest, restrictive mode,
  and readability check.

## Operational Gates

M1 source implementation is complete. Production acceptance requires:

1. review and merge through the VM1-to-GitHub source path;
2. VM2 pull, image rebuild, migration, and API restart;
3. VM1 pull, worker reinstall, unit reinstall, and supervised restart;
4. Prometheus scrape authentication and alert-rule installation;
5. supervised global pause/resume and metrics checks;
6. one backup plus disposable restore drill with recorded evidence.

The continuous worker must remain supervised until those gates pass. Production
database restore remains a separately approved operation.
