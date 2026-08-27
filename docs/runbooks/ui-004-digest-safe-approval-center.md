# UI-004 Digest-Safe Approval Center

## Purpose

Mission Control presents consequential task approvals as a complete, current review envelope. A founder decision is accepted only when it names the exact server-computed review digest shown on screen.

## Review envelope

`GET /v1/approval-center` and `GET /v1/approval-center/{approval_id}` return:

- the immutable task plan digest and current task contract;
- objective, scope, risk, machines, capabilities, outputs and acceptance criteria;
- task prerequisites and mission readiness;
- the active authority-policy digest;
- the active notification generation and duplicate count;
- current, executable and actionable verdicts with explicit blockers;
- prior approval events and the bounded-authority claim.

The `review_digest` covers all fields that can change the meaning or readiness of the decision. A task-contract, prerequisite, mission, policy, approval-state, expiry or notification-generation change produces a different digest.

## Decision contract

Mission Control posts `expected_review_digest` to `POST /v1/approval-center/{approval_id}/{approve|reject}`. The API locks the approval row, recomputes the envelope and returns HTTP 409 when the displayed review is stale. Approval additionally fails unless the gate is current, executable, unblocked and has at most one actionable notification.

Successful decisions append `approval_center_decision_receipt`. Its digest binds the approval, task, action, actor, plan digest, review digest, reason digest and bounded expiry. Approvals authorize one task lease for at most 15 minutes; they grant no broader execution or capital authority.

## User flow

1. Open **Approvals** in Mission Control.
2. Confirm the gate is **Ready**. Blocked gates explain every failed prerequisite and do not expose an enabled approval command.
3. Open **Review & approve** and inspect the full envelope.
4. Acknowledge the exact digest, scope, prerequisites and bounded effect.
5. Record a decision reason and submit.
6. Mission Control reloads the canonical state; decided entries expose the retained receipt.

Review links contain only the approval identifier. They reopen a read-only review fetched from the control plane and never embed a token, action or digest.

## Failure and recovery

- `approval-review-superseded`: reload the center and review the changed envelope; never retry the old digest.
- `approval-not-actionable`: resolve the listed prerequisite, mission, state or duplicate-notification blocker.
- duplicate submission: the approval state transition remains terminal and later attempts fail closed.
- API unavailable: no local decision is inferred or queued.

The legacy `/v1/approvals` endpoint and Telegram digest-bound tokens remain compatible. Mission Control uses only the stricter approval-center decision route.

## Validation

Run unit and integration tests, then execute the no-authority pilot after deploying the API:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/ui004_pilot.py
'
```

The pilot creates a non-executable validation fixture, proves a stale review fails with HTTP 409, rejects the current fixture and retains the digest-bound rejection receipt.
