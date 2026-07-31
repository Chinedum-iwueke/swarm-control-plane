# M12 Research Knowledge Foundation Runbook

## Boundary

M12 provides an immutable, citation-preserving research memory. It does not generate,
approve, execute, or promote hypotheses. A research brief may be created only after the
fixed retrieval evaluation passes against the exact current corpus digest.

Retrieval combines lexical passage overlap with structured section and evidence-type
signals. Similar hypotheses and prior failures come from the immutable M11 registry.
This is intentionally deterministic; semantic embeddings are deferred until an offline,
versioned embedding model and evaluation set are approved.

## Source handling

- PDF passages retain exact PDF page numbers.
- Markdown passages retain section and repository line ranges; they do not invent pages.
- Every document and passage has a SHA-256 digest.
- Evidence is classified as a governing requirement, method, empirical evidence, prior
  result, or operational record.
- Licensed texts and papers are admitted only with a stable source, usage rights, and
  page metadata.

The initial manifest is `worker/knowledge/m12-corpus.json`. Deferred sources are explicit
in that manifest and are not represented as ingested material.

## Deploy

After pulling the reviewed commit on VM2:

```bash
cd /srv/invariance/swarm/control-plane-runtime
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
docker compose up -d --no-deps --force-recreate api
```

The expected migration head is `d4e6f8a0b220`.

## Pilot

Run on VM1 with the protected operator environment. The command ingests the pinned
corpus, evaluates the fixed question set, and creates one traceable brief:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
sudo bash -c '
set -euo pipefail
set -a
source /etc/invariance-swarm/pilot-operator.env
set +a
exec .venv/bin/python scripts/m12_knowledge_pilot.py all
'
```

Do not run `all` twice against the same registry. Immutable duplicate keys are rejected.

## Acceptance

- All four initial documents and their passages are immutable and digest-bound.
- The PRD citations include exact PDF pages.
- The fixed evaluation recall is 1.0.
- The pilot brief is bound to the evaluated corpus digest.
- Each material sourced claim points to a registered passage.
- Uncited analysis is explicitly `agent_inference`.
- Similar hypothesis and prior-failure results derive from M11 registry records.
