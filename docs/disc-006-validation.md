# DISC-006 Validation

Tests cover tautologies, uncovered alternatives/confounders, absent provenance,
post-hoc outcomes, changed decisive tests, incomplete rival results, failed decisive
tests, inconclusive evidence, support, falsification and unresolved conclusions.

Production acceptance requires migration `c6e9f3a52b80`, healthy plan/evaluation routes
and a live no-capital replay proving that failed decisive evidence yields `falsified`
even when other evidence is supportive, followed by an immutable unresolved
supersession.

## Completed evidence

- Core implementation: PR #155, merge `6bdfe7315cceadf29829feb76c6946aefe2a1f61`.
- Live-pilot hardening: PRs #156-#160, culminating in merge
  `6a2aed2fb782baaf42216bb5484f6e0f6b6cc91d`.
- VM2 migration: `c6e9f3a52b80` at the single Alembic head.
- Backend regression suite: 462 passed; focused falsification suite: 10 passed.
- Live report: [`evidence/disc006-report.json`](evidence/disc006-report.json), file
  SHA-256 `48ff260615ce11c722478932b580af51b9e2e0425d28fcd7a853c77530eccdb8`.
- The live replay registered an immutable falsified evaluation and then an
  immutable unresolved supersession. The report records no source-write,
  execution-order or capital authority.
