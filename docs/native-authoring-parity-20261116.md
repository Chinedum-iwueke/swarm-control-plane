# Native Authoring Parity: 2026-11-16

## Question

Can a bounded Codex session reconstruct a known Bulletproof strategy from its
retained card and repository interfaces, both with a direct request and with the
worker's structured engineering prompt?

This isolates authoring competence. It does not test discovery, approval,
requirements review, StrategyIntent scaffolding, independent review, production
task leasing, scientific validation, BT-009 publication or promotion.

## Frozen Experiment

- Bulletproof source: `72dbd592662dc1922e9c144ef69bc58ce5f45af1`.
- Card: `research/hypotheses/alpha_003_btc_5m_impact_proxy_reversal.yaml`.
- Missing implementation: `src/bt/strategy/btc_5m_impact_proxy_reversal.py`.
- Acceptance tests: `tests/hypotheses/test_alpha_003_btc_5m_impact_proxy_reversal.py`.
- Model: `gpt-5.6-sol`; Codex CLI `0.146.0`.
- Runtime: existing Bulletproof virtualenv, `PYTHONPATH=src`, BLAS threads limited to one.
- Budget: one session per lane, maximum 600 seconds each, sequential execution.
- No production API mutations, lake scans, orders or capital authority.

The original native implementation passed all 15 focused tests before the
experiment. Each lane receives a separate tracked-source snapshot with the
implementation removed before initializing a new Git history. Neither fixture
contains the original implementation in its Git history. The missing-module
negative control must fail before a model call is permitted.

Both lanes use the same `EngineeringMissionExecutor._run_author` subprocess
launcher, sandbox configuration, model, runtime and deadline. The direct lane
receives a concise card-to-code request. The worker lane receives
`EngineeringMissionExecutor._coding_prompt` around that same work item.

The benchmark uses the `PARITY-NATIVE` milestone rather than claiming that a
historical card is a newly compiled ALPHA StrategyIntent. Consequently it does
**not** exercise the ALPHA-specific scaffold prompt or full `execute` pipeline.
This is a deliberately narrow first control, not full production parity.

## Acceptance and Evidence

The outer harness reruns the frozen tests independently of the author's reported
result. Acceptance requires a successful author subprocess, passing tests, no
modification or removal of frozen files, and only the permitted new module in Git
status. Tests are visible to both authors; this is not a held-out generalization
evaluation. Network access is disabled for author tools. Cross-checkout copying
is prohibited in the prompt, not proven impossible by a separate read-isolation
container.

Private run evidence is retained at:
`~/.local/state/invariance-swarm/native-authoring-parity-20261116-1/`.
The run contains per-lane prompts, stdout/stderr, negative-control logs,
outer test results, generated implementations and `report.json`.
Generated implementations and raw run artifacts are not committed to this repo.

## Observed Results

| Lane | Author time | Outer frozen tests | Frozen edits | CLI-reported tokens |
| --- | --- | --- | --- | --- |
| Direct request | 151.90 seconds | 15 passed | None | 35,983 |
| Worker structured prompt | 131.20 seconds | 15 passed | None | 28,839 |

Both author processes exited successfully without heartbeat failure or timeout.
Both added only the permitted native strategy module. The direct session's
visible test sequence was 12 passing / 3 failing, then 14 / 1, then 15 / 0;
it repaired its own implementation inside one session. The worker session's
first visible focused test run passed all 15. These are single observations,
not evidence that the worker is generally faster, cheaper or more accurate.
CLI token totals are not billed cost and do not establish cache-adjusted usage.

The benchmark harness and existing rehearsal tests passed: 9 tests total.
The original Bulletproof checkout remained clean. No production candidate,
mandate, task or scientific receipt was created or changed by the benchmark.

**Conclusion:** coherent retained card-to-native-code reconstruction succeeded
through both presentations of the same bounded author runtime. This rules out a
blanket claim that the model or worker launcher cannot do the coding task. It
does not determine which untested ALPHA stage causes current failures. Test the
same accepted contract through scaffold, independent review and native runner
boundaries before expanding autonomous throughput.

## Interpretation Boundaries

One successful paired reconstruction would establish that this model/runtime can
implement this coherent retained contract. It would not establish a success rate,
profitability, scientific validity, general autonomous recovery, or reliable
implementation of newly generated specifications. The next comparison would
hold an accepted current scientific contract fixed while adding the actual
scaffold, review and native-run stages one at a time.

Runner: `worker/scripts/native_authoring_parity.py`.
Fixture isolation regression: `worker/tests/test_native_authoring_parity.py`.

## Downstream Comparison

Runner: `worker/scripts/native_parity_stages.py`.
External regression fixture: `worker/tests/fixtures/native_parity_semantics.py`.
Evidence roots: `~/.local/state/invariance-swarm/native-parity-stages-20261116-1/`
and `~/.local/state/invariance-swarm/native-parity-stages-20261116-repair1/`.

The original implementation and both reconstructions completed `bt.api.run_backtest`
on identical seeded synthetic bytes (6,000 one-minute BTC rows, first frozen grid
variant, identical base engine configuration). Each produced nine trades and
performance, equity, decisions and fills artifacts. This is an engine integration
smoke, not the full card's scientific run, all eight variants, `execute_registered`,
or a production BT-009 receipt. The default engine configuration is not a claim
that every card-level portfolio/scientific constraint was compiled and executed.

Independent read-only Codex review rejected both reconstructions:

- Worker: used strict `>` instead of evaluator `>=` for empirical threshold ties.
  An external deterministic test using exactly representable alternating returns
  reproduced the failure with the frozen 288-bar normalization value.
- Direct: reviewer objected to post-gap ATR initialization. That proposed change
  conflicts with the existing frozen test's assertion that `_ranges` is absent
  after the first post-gap bucket, so it was not applied blindly. Separately,
  differential engine output exposed a real ATR window mismatch: the author used
  the previous 20 buckets, whereas the original native implementation includes
  the completed decision bucket. A new arithmetic test reproduced that mismatch.

Both new tests pass against the original implementation; each reconstruction
fails its respective new test despite passing all 15 original tests. Before repair,
the direct reconstruction matched trade times and sides but not stops, quantities
or net P&L. The worker matched those six fields on the ordinary random fixture,
yet failed the deliberate threshold-tie fixture. Aggregate smoke success alone
therefore misses relevant boundary semantics.

Each repair is bounded to one 180-second author call in the existing workspace,
with the frozen card/tests retained and deterministic failure evidence supplied.
These are new ephemeral model calls with retained files, not resumptions of the
same model conversation. No production campaign retry or approval was created.
Fresh tests, engine execution and independent review follow each repair. The
repaired direct implementation passed 17 tests and matched all six selected
baseline trade fields on the same synthetic panel.

After the bounded repair, **both** lanes passed all 17 tests and matched the
baseline's entry/exit timestamps, side, initial stop, quantity and net P&L across
all nine fixture trades. Neither changed its frozen tests or card.

Fresh reviews still returned `approved: false`; these receipts are retained, not
overridden or represented as accepted scientific review:

- Direct: repeated the first-post-gap ATR objection, plus a NaN OHLC objection.
  Directly injecting a `Bar(high=NaN)` does poison retained ATR state in the
  original and both reconstructed strategies. However, `load_bars` calls
  `validate_bars_df`, which rejects NaNs before the tested file-driven engine
  path. A deterministic loader test passes. This establishes a raw strategy
  boundary hardening issue, not that NaNs reached this engine experiment.
- Worker: claimed closed positions stay in the engine context permanently and
  prevent more than one trade. The native run contains nine trades. Moreover,
  `PositionBook.apply_fill` removes fully closed positions with `_positions.pop`.
  A deterministic open/close lifecycle test confirms removal. The claimed
  permanent-block mechanism is unsupported by that lifecycle; manually injected
  flat mappings remain a separate interface-hardening question.

The direct ATR objection also needs bounded semantic adjudication: its requested
first-bucket state conflicts with the frozen gap test, and its claimed early-entry
effect does not account for the actual 288/2016-bar normalization requirement.
No scientific requirement was rewritten to make a review return approval.

These findings are in `native_parity_invalid_bar.py`: two counter-evidence tests
pass; the deliberately adversarial direct-Bar NaN probe fails on all three
implementations. It is an explicit diagnostic fixture, excluded from normal test
discovery by its filename, not a hidden passing safety test.

**Boundary verdict:** authoring, localized repair and native smoke have concrete
successful observations. Modern evidence-handoff compatibility and reliable
independent-finding adjudication do not. Full canonical suite validation,
scientific terminal outcomes, production publication and autonomous replenishment
were not run or certified by this comparison. Broad engineering was not restarted.

The legacy card also fails modern `preflight_evidence` with
`data_requirements_missing: require reviewed requirements and eligible coverage`.
This is an intentional compatibility probe using a legacy card, not a valid modern
handoff or proof of a newly discovered production bug. It demonstrates that this
successful historical workflow cannot simply be relabeled as modern ALPHA
certification. An explicit, reviewed handoff adapter or modern accepted contract
is required; this experiment does not fabricate missing receipts.

## Architectural Direction Supported by This Experiment

1. Keep a coherent accepted experiment contract and a dependency-complete native
   workspace throughout an engineering work item.
2. Let the author inspect, implement, run fast tests and repair within a bounded
   work budget. Preserve files and diagnostics across model interruptions rather
   than regenerating the strategy from scratch.
3. Add deterministic boundary/differential tests before expensive review. Include
   quantile ties, bar inclusion, gaps, zero/missing inputs and timing semantics.
4. Treat reviewer findings as evidence to adjudicate: reproduce concrete bugs;
   retain contradictions between review, frozen tests and contracts explicitly.
   Do not silently weaken tests or accept the author's self-approval.
   Include the existing validator/loader/position lifecycle guarantees in compact
   review context. Require executable counterexamples or a precise proof against
   supported inputs for blocking claims, and preserve an explicit disputed state
   when the evidence conflicts. This experiment's adjudication was supervised;
   that mechanism is not yet automated in production.
5. Return repairable failures to the same work item with a bounded repair count.
   Keep independent acceptance after repair and durable deferral for genuine
   data, scientific, authority or capacity blockers.
6. Distinguish native engineering readiness, scientific validation and publication.
   A native strategy may be runnable while its modern evidence handoff is absent.

This direction is supported by an offline comparison, not deployed autonomous
recovery certification. The production executor currently returns on independent
review rejection (`EngineeringMissionExecutor.execute`); the campaign's
`_independent_review_correction` gathers findings for successor-task recovery.
Changing that boundary needs a separate tested production increment, with durable
attempt accounting, provider-capacity handling and unchanged approval scope.
