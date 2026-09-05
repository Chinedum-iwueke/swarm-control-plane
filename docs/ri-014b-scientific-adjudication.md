# RI-014B Scientific Adjudication and Learning Loop

RI-014B replaces parser self-scoring with an evidence-bound adjudication loop.

## Trust boundaries

- Representation producers cannot adjudicate their own output.
- Every decision retains reviewer identity, role, rationale, corpus digest, source-region digest, and a hash-chained creation event.
- Conflicting independent decisions remain visible and prevent qualification.
- Recovery workers may submit correction proposals, but proposals remain `pending_approval` and never mutate or publish a representation.
- Corrections must use a new representation version; v1.0, v1.1, and v2.0 evidence remains immutable.

## Benchmark contract

Benchmark membership is selected deterministically per scientific object class with a caller-supplied seed. The sample IDs and sampling algorithm are digest-bound. Evaluation derives classification precision, recall, coverage, abstention accuracy, escape rate, per-type confusion matrices, and Wilson 95% intervals from adjudications only.

A benchmark cannot qualify with incomplete adjudication, reviewer conflicts, or a failed threshold. Parser agreement, parser confidence, and acceptance rate are never treated as ground truth.

## API and operator flow

1. `POST /v1/research/scientific-fidelity/benchmarks` freezes a stratified sample.
2. Mission Control displays unadjudicated `review_required` representations from `/review-queue`.
3. An independent reviewer compares the source region and records one of the six typed decisions through `/adjudications`.
4. `POST /benchmarks/{id}/evaluate` computes the label-derived qualification result.
5. A material mismatch may produce a `/corrections` proposal. Founder approval and a new representation publication remain separate governed actions.
