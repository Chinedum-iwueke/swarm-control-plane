# M14C Operational Memory Steward

## Outcome

M14C adds a durable operational notebook to Hermes without giving a language model
execution authority. A dedicated, signed `vm1-operational-memory-steward` identity can
record evidence-backed observations. The founder can search and manage those records
in Mission Control, and search them from Telegram with `/notes [query]`.

## Trust Boundary

The note body is immutable after creation. Its digest binds the subject, finding,
evidence, affected systems, urgency, proposed owner, deferral context, and milestone
and repository references. Repeating the exact document is idempotent; reusing its
key for different content is rejected.

Lifecycle changes are append-only events. Only the orchestrator surface can assign,
defer, resolve with evidence, or reopen a note. The Steward endpoint can only create
notes and requires both the `operational-memory` capability and an active matching
role-package deployment.

The Mission Control **Plan remediation** action does not dispatch remediation. It
creates a `founder_request` for the Founder Intake Planner. Any resulting proposal
still crosses the normal founder review and approval boundary before a governed task
can exist.

The role package has no workflow, repository access, writable roots, privileged
operations, or direct task-dispatch capability.

## Data Model

`operational_notes` stores the immutable record plus current lifecycle projection.
`operational_note_events` stores every lifecycle transition with actor, reason,
evidence, previous status, new status, and timestamp.

Supported lifecycle actions are:

- `assign`, with an explicit owner;
- `defer`, with a future date and reason;
- `resolve`, with resolution evidence;
- `reopen`, only from resolved state.

## First Note

The first governed record is
[system-wide storage efficiency](notes/system-wide-storage-efficiency.md). It captures
the approximately 27.7 GB Bulletproof research-memory observation without diagnosing
or modifying that database. The M14C pilot gives it an explicit future deferral date
pending an approved measurement, backup, restore, and compaction rehearsal proposal.

## Operator Validation

After deploying the API migration and package source, bootstrap the dedicated identity:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m14c_bootstrap.py \
  --state /etc/invariance-swarm/m14c-steward-state.json \
  --source-commit <FULL_SWARM_CONTROL_PLANE_COMMIT>
'
```

Then create and explicitly defer the first note:

```bash
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m14c_pilot.py \
  --state /etc/invariance-swarm/m14c-steward-state.json \
  --defer-days 30
'
```

Success requires `created` then `defer` events, a stable record digest, visibility in
Mission Control, and a matching `/notes storage` Telegram response.

## Limitations

- M14C is memory and governance infrastructure, not a general autonomous repair agent.
- Search is bounded relational text search; semantic note retrieval is deferred until
  evidence warrants a vector or hybrid index.
- A deferred note does not automatically schedule work when its date arrives. Mission
  supervision should surface overdue notes in a later milestone.
- Notes never authorize repository edits, cleanup, deployments, or data deletion.

## Validation Record: 2026-08-01

M14C passed its operational exit gate against control-plane source commit
`c0d8a2ba617cbb98b406a058ac923cd5b5afedf5` and database migration head
`e1c4a7b92d60`.

- Steward agent: `a159cd80-391c-4a71-bf38-17399043ae05`
- Signed package: `d369d625-7929-42e1-a234-1c38c1f0b772`
- Active deployment: `9eaa33e2-ca1a-4c34-a176-b3da8bc381c1`
- Manifest digest:
  `b1be68f0210fc0f8bede76207a1aba562ef8df314f12147d439a8ef9eb184f6b`
- First note: `3a7a53dc-6182-4a11-b7e0-eb9f9309ef8c`
- Record digest:
  `1cec21b1b177855ebe5bc583da6dd7c369869035e8960fe2b0e71426342a0d8f`
- Lifecycle: `created`, then `defer`
- Deferral end: `2026-08-31T23:12:57.945086Z`
- Credential state: root-owned mode `0600`; credential content was not logged.
- Mission Control: deployed on Mac at the source commit above and confirmed to
  retrieve the exact note ID, deferred status, and record digest.
- Telegram gateway: deployed on VM2 and active after the API migration restart.

No cleanup, compaction, repository edit, task dispatch, or data mutation was
authorized by this pilot.
