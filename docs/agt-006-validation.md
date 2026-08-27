# AGT-006 Validation

Source validation covers:

- enabled-agent, declared-capability, and active-package profile attestation;
- hard rejection of producer or reviewer identity, package, and context reuse;
- deterministic evaluator selection with explicit machine/provider/model/runtime correlation;
- pairwise correlation ceilings and unavailable-independence blocking;
- one evaluator per review kind and no evaluator reuse within a route;
- routed-agent-only completion;
- chained route, assignment, review, and independence-receipt digests; and
- fail-closed independence assertions until every required evaluation completes.

The bounded live pilot reuses the existing M13 statistical reviewer and adversarial auditor. This validates independent routing without inventing duplicate agents. Its successful route permits disclosed shared runtime dimensions; its strict route sets the pairwise correlation ceiling to zero and must block. Neither path has action authority.

Production completion requires migration `d5a9c3e72f10`, a healthy rebuilt VM2 API, and retention of `/var/lib/invariance-swarm/agt006/report.json`. Until that evidence is captured, AGT-006 is source-complete but not production-validated.
