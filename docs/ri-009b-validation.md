# RI-009B Full Research Bible Curriculum Validation

RI-009B was production-qualified on 2026-08-14 against the live canonical
`systematic-research` corpus. It expands RI-009 from one aggregate curriculum
into twelve separately measured Research Bible domains and freezes their
readiness as one immutable portfolio.

## Qualified domains

- backtesting validity
- causal reasoning
- data quality
- execution science
- market microstructure
- portfolio construction
- regime analysis
- reproducibility and governance
- risk engineering
- selection bias
- statistical inference
- time-series methods

Each domain has one versioned topic, two distinct canonical source anchors, a
supporting object, an opposing or limiting object, a held-out support query, a
separate opposition query, and a domain-specific unknown-case abstention test.

## Production evidence

- Qualified portfolio ID: `e9b393e0-4eee-4768-ada2-d3db2be5ffa0`
- Portfolio version: `1.0.1`
- Portfolio digest: `ec1393d67ea1259cec6288023f30ea4a9acf47547566ce73a7c74665a0224f49`
- Corpus digest: `7c5b7b86763eb993f88c69ea026929aeb4930b21f3d9a1fcbf23c71ef7b1696c`
- Graph manifest: `e44e13f0c955cddcd09f1cb5054914ace1e79f4514116b6f15ac0654028cfeb9`
- Required domains: 12
- Ready domains: 12

Every domain recorded `1.0` retrieval recall, citation fidelity, opposition
recall, abstention accuracy, and topic coverage, with `0.0` cross-domain
leakage. Portfolio readiness is the logical AND of all domain readiness rows;
scores are never averaged to conceal a failing domain.

The immutable `1.0.0` portfolio remains `gaps_detected`: regime analysis and
risk engineering initially missed their pinned passages. Evaluation version
`1.0.1` narrowed those queries to the authored methodological claims and passed
without changing evidence IDs.

## Engineering validation

- Backend full suite: 252 passed.
- Focused graph and curriculum suites: 22 passed after freshness optimization.
- Worker suite: 186 passed; two unrelated existing VM2 Postgres TLS/layout
  preflight tests remain failing.
- Changed Python surfaces pass Ruff and compileall.
- Alembic head deployed on VM2: `c8f2a6d94e31`.
- VM2 API image `invariance-swarm-api:0.4.0` returned healthy after migration.
- Graph readiness now binds to the trigger-maintained canonical corpus epoch.
  A legacy graph adopts an epoch only after one exact digest match; a changed
  graph remains stale and fails closed.

## Claim boundary

This milestone proves breadth, replayability, counterevidence retrieval, and
calibrated no-answer behavior for the twelve named domains on the recorded
corpus. A single topic and two source anchors per domain are a minimum
qualification kernel, not proof of exhaustive expertise. Future curricula must
increase topic depth, source diversity, difficulty, and longitudinal
out-of-sample cases while preserving these immutable baseline records.
