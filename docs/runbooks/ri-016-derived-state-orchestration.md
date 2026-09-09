# RI-016 Derived-State Orchestration

RI-016 closes the dependency chain between canonical evidence publication and
the disposable Research Intelligence views that depend on it. Canonical records
remain authoritative and available while derived state converges.

## Runtime contract

PostgreSQL row triggers append object, edge and alias mutations to
`derived_state_changes` at the target corpus epoch. The VM2 orchestrator takes a
transaction-scoped advisory lock, coalesces unclaimed changes and chooses one of
two strategies:

- `incremental` when both projections exist, the change ledger is continuous and
  no more than 5,000 object identities are affected;
- `full` for a first build, forced parity proof, incomplete history or an
  oversized batch.

The durable phase order is retrieval, graph, curricula and verification. Each
completed phase has an immutable digest receipt, so a retry resumes after the
last completed phase. A corpus epoch movement fails the old run closed and lets
the next poll claim the newer epoch. Curriculum evaluations retain their exact
case specifications; affected current curricula can therefore be versioned and
replayed. Legacy evaluations without those specifications report
`awaiting_rebaseline` and prevent a false current claim.

Mission Control schedules the workflow after an inbox or upload publication and
shows the corpus epoch, unclaimed changes, projection freshness, active phase,
strategy and error state. The fleet operation ledger records the same run under
`research_derived_state_reconciliation`.

## Activation

1. Deploy migration `d2e8f5b13a70` and recreate the VM2 API.
2. Install `worker/systemd/install-derived-state-orchestrator.sh --enable
   --start` on VM2 and wait until retrieval and graph report `stale=false`. The
   first pass may honestly finish `needs_attention` because legacy curricula
   do not contain replayable cases.
3. Run `ri009b_curriculum_pilot.py preflight` with the immutable v1.2 catalog
   and anchors. Register it only after all thirteen domain targets are
   retrievable; the production-qualified baseline is RI-009B portfolio `1.2.0`.
4. Let the orchestrator consume the curriculum-state change, then run
   `python -m app.ri016_pilot reconcile`; a current corpus must return
   `no_change`, while a changed corpus must reach `succeeded`.
5. After an incremental run, execute `python -m app.ri016_pilot parity`. The
   retrieval and graph content digests must match the clean full rebuild.

If the replayable baseline reports `gaps_detected`, run
`ri009b_curriculum_pilot.py diagnose`. It emits the pinned opposing objects,
their current rank and provenance-bearing excerpts, actual top hits and any
registered domain missing from the portfolio catalog. Author a new immutable
curriculum version from that evidence; never relax a threshold or overwrite the
failed evaluation.

Rollback disables the orchestrator and uses the existing full retrieval and
graph rebuild operations. It never removes or rewrites canonical evidence or
the retained reconciliation receipts.

## Production closure

On 2026-09-09 the live corpus at epoch `577353` reported zero pending changes
and `current=true`. Forced-full run `43885a98-501b-436a-9162-6f8fe4c9cdd5`
then reproduced the current retrieval digest
`1ba49d4e2368a78fdace74ca5d865b58ba92e6f249a3202275f119c6e06e26ea`
and graph digest
`c0eaf61a7a01d5058637206abf2bef575f784efb33d9c296ef9a298eb0ea1988`
exactly. Its terminal outcome was `succeeded` with
`incremental_full_digest_parity=true`; this is the production parity receipt.
