# Coverage-aware successor planning

Status: planning, durable publication, independent-review routing and bounded
successor materialization implemented. Production scientific certification is
not established by these implementation tests. No existing candidate dates,
task approvals or mandate digests were rewritten.

## Policy

New CLI mandate proposals request a 1095-day historical envelope ending at the
preferred latest-year end, at most two coverage successors, and no outcome-based
window search. `--coverage-lookback-days` can reduce the envelope. The primary
scientific duration remains 365 days; a three-year selection envelope does not
authorize three-year experiments or extra trials. Approval of the new mandate's
exact digest is still required. Renewal of a legacy mandate preserves its legacy
scope, rather than granting new authority silently.

`AlphaCoverageReplanningPolicy` validates timezone-aware, bounded envelopes.
`coverage_window` preserves frozen dates when a mandate lacks this permission.
`alpha004_mandate.py` now includes all timestamped successful registered OHLCV
panels in the requested venues in discovery scope, even with reported gaps or
short histories. `discovery_panels` and `_candidate_reasons` route these panels
to content-bound admission instead of assuming they are scientifically eligible.
Stable/volatile labels are not scope boundaries. Unregistered files still require
registration; unknown venues do not acquire authority.

## Native successor contract

Bulletproof `bt.governance.coverage_successor.plan_coverage_successor`:

1. Replays the parent scientific plan against its frozen requirements, basket,
   source commit, budgets and coverage receipts.
2. Accepts only a coverage-only failure, not low returns, insufficient events,
   compute exhaustion or a changed hypothesis.
3. Checks the bounded lineage and a complete, digest-bound exposure ledger.
4. Removes exposed intervals conservatively, including non-bar-aligned cuts.
5. Chooses the latest sufficiently long common interval within the authorized
   envelope, retaining warmup, purge, embargo, target tail and support requirements.
6. Produces an immutable successor proposal with an ordinal and parent digest.
   Unchanged evidence cannot generate an endless retry chain.

The scaffolder can emit this proposal before any paid authoring when supplied
`coverage_successor_context`. The original preflight still fails closed: a
proposal is not execution approval. Its `planning_inputs` permit deterministic
replay of the proposed scientific plan.

## Durable recovery

The engineering worker retains the deterministic preflight and successor proposal
in its failed task summary. Campaign reconciliation publishes the proposal in
the existing hash-linked campaign event ledger under the campaign row lock. It
routes spec and causality reviewers using the existing independent identity and
package checks. Coverage review is explicitly distinct from implementation review.
Only two approving verdicts can create a `-COV1` child with one execution attempt.
Its exact window and receipt are frozen in a new task contract. Reconciliation
returns that child on repeated calls; it never mutates the failed parent.
Routing failure or rejection is visible as a blocked/needs-attention state.

The native producer streams minute data in at most 100,000-row chunks aligned to
the research clock and applies transformations after joining completed bars.
Total source work and retained research rows remain bounded independently.
Chunked and single-read output digests are regression tested for equivalence.
Admission supports up to 128 assets; this does not bypass the mandate's basket
limit or resource admission. High-frequency large baskets can still defer when
the retained research-row budget is insufficient.

## Production qualification boundary

- The campaign service must supply authenticated, independently reviewed
  `validation_requirements`, `coverage_successor_context`, and the complete durable
  exposure/lineage ledger. A caller-provided digest is not proof of authenticity.
- Existing tasks without that reviewed package are not silently grandfathered or
  mutated. The production publisher for those upstream inputs remains a separate
  outstanding commissioning dependency; this recovery deployment does not invent
  their missing receipts or approve a wider mandate.
- Predictor coverage still needs point-in-time membership verification and an
  explicit distinction between source warmup and finite-feature eligibility.
- Demonstrate the TRB and basket successors using real receipts, then run smoke
  and scientific validation. Metadata extents alone are insufficient evidence.

These changes remove discovery-time full-year/gap filtering, not DATA-003 quality,
resource admission, scientific review, or mandate approval boundaries.
