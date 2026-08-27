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

Production completion was observed on 2026-08-27. VM2 runs migration `d5a9c3e72f10` and healthy API image `sha256:c1bd88e3a5f927da5e7e0565bac095f7d7368e3ef60476bcf0bb862ff4c7a07e`. Route `68fd264d-f956-477a-8d8c-90946d5a7716` completed statistical and adversarial assignments across two distinct agents and two distinct package digests, issuing independence receipt `9ed893dd2c37fd7cc51605416966ccbd5cd2e41a6e5b53d0a4e333f69b221d86`. The zero-shared-dimension control route blocked as `independent_evaluator_unavailable`, accurately retaining the current shared machine/provider/model-family risk. The root-owned report remains at `/var/lib/invariance-swarm/agt006/report.json`; its retained repository copy is `docs/evidence/agt006-report.json`, file SHA-256 `fd255e60a6b08744e55265afce8f9ba408e000eeff0c4685502c2ce39643b29a`, canonical report digest `9f5462ac1c665c1b878086d6662c309f58ab8e92247e70e4ff25f80f4eb5169a`, and `action_authority` is false.
