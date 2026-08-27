# DISC-008 Validation

- Exact agenda-to-task-graph binding and explicit no-capital authority.
- Fixed task, attempt, duration, reconciliation, stall and worker-loss budgets.
- Digest-chained session registration, checkpoint, progress, escalation and closeout events.
- Scope drift, conflict, no progress, worker loss and task-graph failure fail closed.
- Graph success remains `awaiting_closeout` until AGT-006 and DISC-007 evidence is bound.
- Operator cancellation cancels remaining graph work without deleting outcomes.
- No approval, scope expansion, promotion, order or capital authority.
