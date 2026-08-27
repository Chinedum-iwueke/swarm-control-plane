# AGT-002 Validation

- Context manifests bind task, agent, attempt, authorization snapshot, exact rendered pack, expiry, and two integrity digests.
- Source records bind provenance, selection reason, sensitivity, prompt position, citation coordinates, and selected contradictions.
- Protected, inactive, contaminated, ambiguous, expired, and oversized context fails closed.
- The restricted worker materializes required context once with mode `0600` before execution.
- Working-memory content remains task-local; the control plane retains digest-only receipts.
- Task complete, failure, and release discard active working-memory receipts without deleting canonical evidence.

## Live validation

VM2 migration `a2d6f9c41e80` is current and API image `sha256:0bfe3e758be878a6a097f3e3700e81a140c8d75e5f2f813e08bcca67a37fb5be` is healthy. The no-execution pilot retained [its digest-bound report](evidence/agt002-report.json): exact replay was true, scratch content was absent from the control plane, one receipt was discarded, and the non-leaseable pilot task ended cancelled with no execution or capital authority.
