# M3 Approvals and Artifact Evidence Runbook

## Approval Boundary

Set `approval_required: true` when creating a task that must not lease without a
founder decision. The control plane computes a canonical SHA-256 digest over
the execution plan and creates the task in `pending_approval`.

An approval:

- binds the exact plan digest, risk, project, task type, and input contract;
- records approver, reason, issue, and expiry;
- creates a random execution nonce and stores only its SHA-256 digest;
- is consumed atomically by the first lease;
- cannot be reused after lease release or expiry.

Released or expired approved tasks return to `pending_approval`. Rejection
cancels the task. Revocation is permitted only before consumption.

## Operator Commands

Use the protected operator environment and:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
.venv/bin/python scripts/governance.py approvals
.venv/bin/python scripts/governance.py approve \
  --approval-id APPROVAL_UUID \
  --reason "Reviewed plan and bounded impact"
.venv/bin/python scripts/governance.py events \
  --approval-id APPROVAL_UUID
```

Use `reject` or `revoke` with the same ID and a recorded reason.

## Artifact Evidence

While a lease is valid, the worker hashes each complete stdout/stderr log and
registers:

- task, agent, and attempt;
- artifact type, name, byte size, and SHA-256;
- workflow package version and source commit;
- storage location and backend;
- confidentiality, retention, and verification state.

Only `workspace://` and `object://` locations are accepted. The API registers
metadata and never dereferences worker paths. Large files belong in reviewed
object storage; PostgreSQL remains the provenance authority.

Inspect:

```bash
.venv/bin/python scripts/governance.py artifacts --task-id TASK_UUID
```

Migration `f4c8d1a72b60` must be applied before deploying the API and worker.
Validate with one approved success task, one rejected task, one expired/released
approval, and digest comparison against the preserved workspace logs.
