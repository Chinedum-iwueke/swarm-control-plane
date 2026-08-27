# AGT-002 Validation

- Context manifests bind task, agent, attempt, authorization snapshot, exact rendered pack, expiry, and two integrity digests.
- Source records bind provenance, selection reason, sensitivity, prompt position, citation coordinates, and selected contradictions.
- Protected, inactive, contaminated, ambiguous, expired, and oversized context fails closed.
- The restricted worker materializes required context once with mode `0600` before execution.
- Working-memory content remains task-local; the control plane retains digest-only receipts.
- Task complete, failure, and release discard active working-memory receipts without deleting canonical evidence.
