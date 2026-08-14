# RI-009 Domain Curriculum and Brain Evaluation

## Purpose

RI-009 qualifies a research domain from measured evidence coverage and held-out
retrieval behavior. It does not grant authority to an agent, infer expertise from file
count, or let source text modify policy.

## Lifecycle

1. Reconcile ingestion and settle every source as canonical, duplicate, quarantined,
   superseded, excluded, or failed.
2. Rebuild retrieval and graph projections and retain both digests.
3. Register an immutable curriculum version with an acyclic topic/prerequisite graph.
4. Bind every topic to canonical evidence and, where required, opposing evidence.
5. Run held-out answerable, adversarial, cross-domain, and abstention cases through the
   canonical hybrid retrieval service.
6. Compare measured recall, citation fidelity, opposition recall, abstention accuracy,
   leakage, and topic coverage with declared thresholds.
7. Qualify only when every threshold passes. Any corpus or graph digest change makes
   the qualification stale until reevaluation.

## Operational checks

```bash
curl -fsS -H "Authorization: Bearer $SWARM_ORCHESTRATOR_TOKEN" \
  "$SWARM_API_URL/v1/research/curricula/readiness"
```

Mission Control shows the latest curriculum version, topic coverage, quarantined item
count, projection digest, and explicit readiness blockers.

## Security boundary

- Curriculum sources are canonical object IDs, never arbitrary filesystem paths.
- Source authority classes are allowlisted by the curriculum rubric.
- Evaluation queries are data; they cannot create tasks or change authority.
- Returned citations must replay to the same canonical object and digest.
- Forbidden evidence measures cross-domain leakage.
- Unknown questions must be present in every evaluation set and must produce an
  abstention.
- Failed evaluations remain retained evidence and do not activate a curriculum.

## Rollback

The migration is additive. Before production curricula are registered, downgrade one
revision to remove only RI-009 tables. After records exist, preserve them and disable
the routes instead; do not erase qualification history.
