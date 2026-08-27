# DISC-008 Bounded Autonomous Research Sessions

DISC-008 coordinates a frozen AGT-003 task graph through an unattended, no-capital
research session. It does not create an alternate executor, approve work, expand scope,
select a winner, promote a result or interact with capital.

## Contract

1. Register an unactivated risk-zero task graph whose ordered nodes exactly match the session agenda.
2. Freeze task, attempt, duration, reconciliation, no-progress and worker-loss budgets.
3. Activate the graph through the session endpoint and reconcile it through the existing graph controller.
4. Record progress, no-progress, conflict and worker-loss checkpoints with evidence digests.
5. Escalate and cancel remaining work on drift, conflict, stalls, worker-loss excess or budget exhaustion.
6. Retain positive, negative, invalid, failed and cancelled outcomes.
7. Complete only after an AGT-006 independence receipt and active DISC-007 selection audit bind the closeout dossier.

## Rollback

Cancel the session. The controller requests cancellation for running tasks, cancels
unleased work and invokes declared graph compensation. Session, task, message and event
lineage remains immutable and replayable.
