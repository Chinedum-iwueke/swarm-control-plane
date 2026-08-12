# RI-008 Knowledge Graph Operations

## Boundary

Canonical evidence objects and canonical typed edges in PostgreSQL are authoritative.
The knowledge graph node and edge tables are versioned, disposable projections. They
must never be edited directly or used to create canonical facts. Model output cannot
register an edge without the existing authenticated write boundary and typed contract.

Traversal filters projects, node access classes, edge access classes and provenance
objects before expanding any path. A missing or stale projection fails closed. Temporal
edges use a half-open interval: `valid_from <= as_of < valid_until`.

## Deploy

Deploy the API and apply Alembic revision `6e8a1c4d9b20`. Rebuild the projection only
after the migration and canonical corpus reconciliation are complete:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
.venv/bin/python scripts/ri008_graph_pilot.py
```

The pilot rebuilds the graph, samples canonical replay, and executes the deterministic
mean calculator. Retain its JSON output with the deployment evidence. It never prints
the operator token.

## Recovery

After canonical restore, rebuild retrieval and graph projections. Compare the graph
manifest's canonical corpus digest, node count, edge count and sampled replay digests
with the retained receipt. Do not serve graph answers while the status endpoint reports
`stale=true`.

Rollback removes only RI-008 projection and tool-receipt tables plus additive edge
metadata. Canonical evidence objects and the original subject/predicate/object edge
identities remain intact.
