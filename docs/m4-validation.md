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

## Production Deployment

- VM2 API version: `0.3.0`;
- Alembic head: `a1d9e5f63c20`;
- role package: `vm1-engineering-worker` `1.0.0`;
- role package digest:
  `11bf02083ecfad5e0edb7baf1f432e4305b743cb20126481be5414ee362a1ea4`;
- agent: `vm1-developer-coder`;
- dedicated Codex CLI: `0.146.0`;
- worker systemd unit: installed, disabled, and inactive during validation.

## Pilot History

The first signed mission, `ef16ced8-778e-400c-b3b9-c7f568fc4632`, failed
closed because Codex CLI `0.130.0` did not support the configured model. Task
`12858249-e742-4f68-ba91-c9818ddf3322` failed once without changing either
checkout. Codex was upgraded and its dedicated login retained.

The first retry, `5d92ea3d-ed5a-4787-a977-c130e97edc5b`, proved that coding
and scope enforcement worked, then failed closed because the shared named
validation executor accepted only `code_validation`. Task
`7ec8f145-308c-4d51-aae6-ea9ca5f5ec0c` changed only the allowed file in its
isolated worktree. The integration guard and mission-state refresh defects were
fixed with regression coverage. Both failed missions are `blocked`; neither has
a completion event.

The final signed mission, `ab8b825f-88f0-4897-9d9b-da12ae7fec24`, succeeded.
Task `f75a2297-0c48-4705-ad0f-b245726ce549` was assigned to
`vm1-developer-coder` and completed on attempt one.

Event order:

1. `task_created`
2. `mission_task_planned`
3. `task_leased`
4. `task_started`
5. three `task_heartbeat` events
6. `task_completed`
7. `mission_succeeded`

## Pilot Evidence

- resolved base commit:
  `c2e2995ee51f202d9ccca6e8cb8fe65d365b3c3b`;
- changed path: `docs/m4-engineering-pilot-result.md`;
- changed files: one;
- diff size: 37 lines, below the 120-line ceiling;
- isolated tests: 119 passed with two existing deprecation warnings;
- compile step: passed;
- independent review: approved with no findings;
- registered records: ten logs and four evidence/result artifacts;
- `changes.patch`:
  `7de761dbe09c0a09c1fc1dc87684ad5185ea6ef495e3b4e77a2da2d2b81204a9`;
- `review.json`:
  `9628ac0a3d71c48d08edc4032b40ea74e2a57cb4f7e3f7768b38aa3267c6f4b6`;
- `pr-bundle.json`:
  `10f961aeff5cb8cde79b6c6e96bb829021810a94db9654cf4db72b7b0f2b258e`;
- registered digests match the preserved workspace files;
- sensitive token and authorization-pattern scan: zero matches;
- primary checkout: clean and unchanged;
- no push, merge, deployment, or remote mutation occurred.

## Automated Evidence

- worker tests after pilot fixes: 103 passed;
- backend tests after pilot fixes: 16 passed;
- worker and M4 backend Ruff scopes: passed;
- worker compileall and mission CLI compilation: passed;
- systemd unit verification: passed;
- Alembic graph: one head, `a1d9e5f63c20`;
- prohibited command and sandbox-bypass scan: passed;
- Git whitespace validation: passed.

The two backend test warnings are existing Starlette deprecations and do not
change M4 behavior.

## Recommendation

GO for founder-reviewed adoption of the generated patch and controlled
single-task engineering missions. Continuous worker activation is acceptable
after the stale pre-M4 validation lease is reaped or cancelled and an operator
confirms the queue contains only intended work. Keep one-task concurrency,
preserve workspaces, and retain human review before applying any generated
patch.

Known limitations remain: M4 creates a local patch and PR bundle but does not
open or merge a GitHub pull request, object storage is not configured, workspace
retention is manual, and the bounded API result reports worker version
`unknown` even though role-package attestation records worker `0.3.0`.
