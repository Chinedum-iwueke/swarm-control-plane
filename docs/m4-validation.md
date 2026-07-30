# M4 Engineering Mission Validation

Date: 2026-07-30

## Source Controls

- strict, cycle-checked milestone manifests;
- founder approval reference, canonical digest, and separate HMAC signature;
- mission budgets, stop conditions, path boundaries, and task attempts;
- PostgreSQL task dependencies enforced during leasing;
- append-only mission creation, completion, and blocking events;
- isolated Codex workspace-write coding session;
- minimal child environment and dedicated Codex identity;
- independent named workflow validation;
- separate ephemeral review session;
- changed-file and diff-line enforcement;
- local patch and PR bundle with registered digests;
- no push, merge, deployment, or primary-checkout mutation.

## Operational Gates

Production pilot acceptance requires deployment of M1-M4 migrations and role
package `vm1-engineering-worker` `1.0.0`, dedicated Codex login, one supervised
mission, artifact digest comparison, primary-checkout verification, and founder
review of the bundle.

## Automated Evidence

- worker tests: 102 passed;
- backend tests: 15 passed;
- worker and M4 backend Ruff scopes: passed;
- worker compileall and mission CLI compilation: passed;
- systemd unit verification: passed;
- Alembic graph: one head, `a1d9e5f63c20`;
- prohibited command and sandbox-bypass scan: passed;
- Git whitespace validation: passed.

The two backend test warnings are existing Starlette deprecations and do not
change M4 behavior.
