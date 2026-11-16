# Strategy engineering: retained SPX/BTC failure

## Observed evidence

Task `A3-6b49fb31-001-G3` (53a46fd1-0c24-4e2d-8cb9-a9ee98d63b52)
failed on attempt two at 2026-11-16 04:05:59 UTC. The failed step was
`focused-strategy-tests-after-correction`, return code -15. The worker's focused
test budget was 300 seconds; the logs contained five completed tests and no
assertion failure. This is a test-runtime timeout, not a rejected research result.

Before correction, five tests passed in 189.16 seconds under trusted
instrumentation, but recorded zero native runner calls. The coverage gate
correctly rejected that suite. The correction added a real `execute_registered`
test, with two 1m synthetic panels covering 196 four-hour bars and four variants.
That is 47,040 source minutes per asset, or 376,320 asset-minute-variant rows before
additional representation, provenance and evaluation work, not merely 1,568
research-bar-variant observations.
It still omitted both `run_native_case` and `run_scientific_case`; therefore even
finishing that integration test would not satisfy the required terminal harness.

A bounded diagnostic rerun of the retained five non-runner tests passed in 72.55
seconds (137892 KiB peak RSS for the process). This is not a speed benchmark
against the earlier run: the patch and instrumentation differ. No real market
outcome was evaluated by this diagnostic.

The repaired prerequisite gate rejects this exact retained test file in 0.473
seconds, before importing or executing any tests. It identifies the two missing
harness calls. No authoring call was used for this diagnosis. Historical failure,
mandate counters and candidate contracts remain unchanged.

## Shared repairs

- `strategy_test_probe.py`: AST prerequisite check before expensive pytest work.
  Direct imports, aliased imports and attribute calls are recognized. This is not
  proof of coverage: runtime observation still rejects dead/mocked calls and
  requires all four retained outcomes plus a genuine runner smoke result.
- Per-test start/completion, durations and periodic traceback diagnostics make
  resource failures observable instead of leaving only pytest dots.
- `engineering_mission.py`: timeout receives its own failure category and does
  not automatically invoke paid code correction or another full authoring retry.
  Scope-checked patches are retained on focused-test timeout/corrected-test failure
  as unapproved recovery material, not a successful implementation bundle.
- Correction instructions explicitly reiterate the required harness APIs.

These changes reduce wasted retries; they do not complete the candidate's tests,
approve its code, or certify its scientific execution.

## Staged Validation Repair

Worker validation now separates unmarked unit tests (300 seconds), tests marked
`pytest.mark.native_smoke` (900 seconds), and tests marked
`pytest.mark.scientific_terminal` (1800 seconds). Each allowance is capped by the
remaining immutable mission deadline; an exhausted deadline starts no process.
These are separate subprocess stages in one mission, not independently scheduled
or resumable jobs. Completed stage results are retained in an artifact JSON.

The trusted runtime probe rejects native calls in the wrong stage. Smoke must
complete both the real runner and smoke harness; the scientific stage must retain
all four scientific outcomes. Empty stages fail. No gate is replaced by a pytest
marker alone. Timeout still retains the patch without invoking paid correction.

New campaign tasks explicitly distinguish short native smoke from full-length
scientific fixtures. Historical task acceptance criteria remain immutable. New
tasks also require a cheap canonical-grid/envelope check before native execution:
the SPX/BTC diagnostic reached all four engine variants but then failed because
the evaluator enumerated the same parameter tuples in a different order from
Bulletproof's compiler. This diagnosis is not a scientific negative result.

## Architectural priorities

1. **Platform-owned test protocol.** Move fixture binding, review-packet assembly,
   terminal assertions and runner orchestration out of authored test boilerplate.
   Authors supply typed scenario factories and expected outcomes, while immutable
   platform tests invoke them. Keep semantic assertions independent of the author.
2. **Separate validation jobs.** Fast unit/contract tests, real native smoke and
   long-horizon synthetic evaluation need separate resource budgets and receipts.
   Source-minute rows, basket size, variants and bootstrap repetitions all affect
   cost; research-bar counts alone understate work. Never shrink scientific support
   or relax causality merely to fit a five-minute authoring gate.
3. **Typed recovery routing.** Contract defects go to bounded code correction;
   resource/timeouts go to deterministic profiling and capacity planning; quota
   goes to provider deferral; scientific negatives go to memory. A timeout is not
   evidence that an LLM should rewrite the strategy.
4. **Checkpointed repair, not regeneration.** Bind each scope-checked patch to its
   source, intent, failed check and parent task. Reuse unchanged validation evidence
   only when all relevant digests match. Never rewrite a completed attempt.
5. **Instance-aware draining.** The current engineer replicas share an agent
   identity. Agent-level task lookup cannot identify the busy systemd instance.
   Add instance IDs and drain acknowledgements before future rolling restarts;
   until then inspect process/cgroup ownership and avoid restarting busy workers.
6. **Measured acceptance.** Track first-pass contract compliance, native harness
   completion, correction count, model usage per accepted bundle and timeout cause.
   Successful authoring processes are not successfully engineered strategies.

Items above are recommendations, not claims of implemented scheduling or fixture
factory support. Next candidate repair must implement the missing harness cases,
then measure native integration cost before admitting a bounded successor. Do not
reset the failed task or launch another full authoring run simply to clear its
status. No architecture can guarantee every proposed strategy is feasible or
scientifically valid; it can guarantee failed gates cannot be silently promoted.
