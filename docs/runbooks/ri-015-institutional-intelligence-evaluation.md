# RI-015 Institutional Intelligence Truth Evaluation

RI-015 measures what a named Research Intelligence runtime can retrieve, relate,
cite, calculate and decline to answer. It does not infer reasoning competence
from ingestion counts, curriculum coverage, parser confidence or prose quality.

## Contract

- Suites bind hidden gold items to exact corpus and projection digests.
- Public suite responses expose item identity, domain, task type and prompt digest,
  but never gold answers.
- Runs cover the exact suite manifest and retain model/runtime identity, evaluator
  identity, structured response evidence and item-level result digests.
- Suite authors cannot evaluate their own suite.
- Corpus or projection drift makes a run `stale`, never qualified.
- Metrics cover citation entailment, answer completeness, unsupported-claim
  control, abstention calibration, formula accuracy, table accuracy, ordered
  multi-hop path validity and latency compliance.
- Aggregate scores include only applicable items. A direct-citation question does
  not receive free formula, table or graph-path credit.
- Score thresholds are complete and bounded, and a run that regresses beyond the
  suite's declared tolerance fails closed even if it still clears an absolute
  threshold.
- Every domain is independently `qualified` or `not_demonstrated`; representative
  failures and limitations remain visible.
- Contract fixtures can validate evaluator behavior but can never qualify the live
  institutional brain.

## Production sequence

1. Deploy migration `c1d7e4a92f60` and rebuild the API.
2. Run `python -m app.ri015_pilot` to verify the evaluator contract. Its readiness
   status must be `contract_validated`, with a limitation stating that live
   intelligence is not demonstrated.
3. An independent evaluation owner registers a `live_corpus` suite containing
   domain-stratified, hidden, adjudicated items at current corpus/projection
   digests.
4. Execute the candidate runtime without exposing hidden gold fields, then submit
   its structured responses and immutable runtime digest.
5. Inspect `/v1/research/intelligence-evaluation/readiness`. Only an exact,
   non-stale live run meeting every declared threshold may report `qualified`.

Rollback removes only RI-015 derived evaluation tables. It preserves the corpus,
retrieval/graph projections, RI-014 evidence and all source artifacts.
