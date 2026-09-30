# Book XI: Codex and LLM Runtime Register

This register names every production path where a language model performs real work.
The deterministic control plane, Bulletproof engine and canonical evidence remain
authoritative. LLM output is a proposal, transcription, implementation draft or review;
it is never a backtest result, risk decision, promotion decision or order instruction.

| Runtime | Invocation | Real role | Writable scope | Required downstream authority |
| --- | --- | --- | --- | --- |
| Founder planner | `worker/src/swarm_worker/planner/engine.py` | Turns a founder conversation into a bounded decision brief or proposal | Structured response only | Digest-safe founder approval before execution |
| Research Intelligence director | `AlphaDiscoveryExecutor`, stage `intelligence` | Synthesizes cited mechanisms, contradictions, prior failures, observations and portfolio gaps | Structured cited brief only | Deterministic citation and mandate checks |
| Senior researcher | `AlphaDiscoveryExecutor`, stage `hypothesis` | Proposes predictive, timed, falsifiable questions and mechanisms | Structured candidate questions only | Falsifiability, novelty, equation and data gates |
| Governed external research | `ri017_external_acquisition.py` and RI-006 ingestion | No LLM is invoked during fetch, parsing, transcript extraction, quarantine or publication. Sanitized source metadata may later be supplied to the Research Intelligence director and senior researcher as untrusted question-seed context | Immutable retrieval receipts and quarantined publications only | Source allowlist, SSRF/size/content controls, replayable provenance and normal ALPHA-004 gates |
| Data representation scientist | `AlphaDiscoveryExecutor`, stage `representation` | Selects pre-outcome baskets, member roles, clocks and a typed transformation graph; may use or cross optional stable/volatile labels when justified; records rejected alternatives | `adaptive-representation-plan-v1.0.0` only | Catalog-label validation, exact DATA-002/003 panel admission, native causal replay, exact strategy-consumer binding and terminal BT-009 evidence |
| Strategy engineer | `EngineeringMissionExecutor`, coding session | Drafts an exact native Bulletproof hypothesis contract, strategy and tests in an isolated worktree | Approved paths and diff budget only | Tests, independent review, PR/merge and source-commit rebinding |
| Engineering reviewer | `EngineeringMissionExecutor`, review session | Reviews the uncommitted engineering patch against its immutable acceptance contract | Read-only | High findings fail the task; it cannot merge or approve itself |
| Strategy-spec reviewer | `AlphaStrategyReviewExecutor` | Independently critiques native strategy/spec equivalence and reproducibility | Structured review only | Separate evaluator profile and controller reconciliation |
| Causality/leakage reviewer | `AlphaStrategyReviewExecutor` | Independently checks timing, leakage, target and implementation equivalence | Structured review only | Separate evaluator profile and controller reconciliation |
| PDF recovery adviser | `backend/app/ingestion/recovery_controller.py` | Classifies bounded ingestion failures and proposes recovery actions | Recovery recommendation only | Deterministic sanitizer/parser policy; no canonical overwrite |
| Mission Control research copilot | `mission-control/src/hermes_mission_control/research_copilot.py` | Explains visible research evidence to the founder | UI response only | No task, approval, capital or order authority |
| Codex authentication watcher | `worker/src/swarm_worker/codex_auth_watcher.py` | Executes a minimal fixed-output probe to distinguish a usable server-side session from stale local login state | Fixed probe output and redacted recovery state only | Authentication continuity only; it cannot reason about research, edit code, approve work or consume an experiment attempt |

## Authentication continuity

The shared VM1 Codex runtime is supervised by
`invariance-swarm-codex-auth-watcher.service`. The watcher performs a real, minimal
`codex exec` probe under the same credential-refresh lock used by discovery and
engineering. `codex login status` alone is not accepted as proof because a locally
present session can still have a rejected server-side credential.

On a confirmed authentication rejection the watcher opens one durable recovery
incident, starts the official device-authorization flow and publishes only the OpenAI
verification URL, short-lived device code and expiry through Mission Control and the
restricted founder Telegram channel. Access, refresh and identity tokens never enter
the control plane, Telegram or Mission Control. An expired attempt stays attached to
the same incident; `/codex-login retry` or Mission Control's `New code` command asks
the watcher for a fresh generation. The runtime returns to `healthy` only after the
real probe succeeds. Authentication recovery does not approve tasks, consume campaign
attempts or grant research, shadow, order or capital authority.

The watcher, Telegram recovery command and Mission Control recovery panel were
production-observed on 2026-09-27. VM2 runs migration `d3b9f5a72e10`; the VM1
watcher returned to `healthy` after device authorization; the restricted Telegram
gateway exposed the same incident; and Mission Control exposed the current state and
same-thread retry command. This observation proves the recovery path at that time,
not permanent provider availability.

## Deterministic boundary

Codex does not calculate performance metrics, resample bars, select winners after
outcomes, issue BT-009 receipts, grant promotion, set risk, reconcile positions or
place orders. Bulletproof-native code performs data transformation and backtests from
immutable contracts. The control plane enforces budgets, authority, independence,
lineage and lifecycle transitions. New code, expanded data authority, shadow admission
and every capital action remain explicit gates.
An LLM may propose fractional differentiation, returns, local scaling or a cross-asset
representation, but it may not tune those choices against targets or held-out results.
The native compiler validates parameters, materializes complete bars, aligns panels,
and exposes fields only at their decision timestamps.

The senior researcher receives the exact native Bulletproof mechanism catalog in
addition to citations, prior outcomes, signal screens and execution observations.
Declared CSI components, indexes, proxies, gates and failure modes are reasoning
material, not empirical facts. The LLM may propose adapting or falsifying them, but it
cannot assert that CSI or another proxy is predictive, select it after viewing outcomes,
or bypass native calculation and independent review.

The representation scientist may propose 1-100 instruments by default, including
cross-label baskets, and may select any supported complete-bar timeframe or admitted
causal transformation. Its justification is model output. Deterministic catalog,
common-window, liquidity, lineage, capacity and point-in-time validators decide whether
the proposal can execute. Primary tests use 365 UTC days ending immediately after the
newest gap-free DATA-002 cataloged minute; up to 1,095 days requires a separately
frozen survivor-validation contract.

Low-watermark replenishment is deterministic orchestration, not LLM self-direction.
When accepted or awaiting question depth drops below the approved threshold and
parallel campaign capacity remains, the controller invokes another bounded
intelligence, hypothesis and representation sequence immediately. The mandate
objective and budgets remain the authority envelope.

## Evidence requirements

Every invocation binds a source commit, role package, model/runtime identity, task
contract and retained output. Agent reasoning must be replayable from supplied context.
Scientific equations require deterministic or genuinely independent assurance; an LLM
cannot verify its own transcription. Failed, rejected and invalid outputs remain part of
institutional memory and novelty scoring.

## Durable remediation rule

An error discovered by an experiment must be classified before correction. A defect
in dispatch, evidence binding, lifecycle accounting, outcome taxonomy, held-out
evaluation, logging, resource control or validation belongs in the shared producer or
validator, not in a one-off strategy patch. Closure requires a regression for the
original failure and a second materially different hypothesis, asset, timeframe or
failure fixture that proves the invariant generalizes. Hypothesis-specific predictors,
targets and mechanisms remain in their native card and strategy module.

The multi-asset engineering sequence demonstrates why this boundary matters. Three
generated revisions passed deterministic tests but were rejected by independent
scientific review because direct unit coverage concealed a runner grid-type mismatch,
caller-derived evidence digests, an incompatible logging contract, an unused grid
dimension and missing runner-level coverage. Those rejected bundles remain evidence.

Bulletproof PR #341 subsequently repaired the shared contracts rather than special-
casing one campaign. At merge commit `8207ee4e4256ff733df2e6bde4bb4af05c579134`,
every fully provenance-bound native contract is checked against immutable lake bytes,
receipt and lineage fields; complete-hour construction is gap-safe; purge and embargo
use elapsed time; held-out access remains sealed; terminal positive, negative, invalid
and failed outcomes share the logging contract; and runner-level mutation tests reject
binding drift. The complete native suite passed with 1,786 tests, 34 skips and no
failures. This qualifies the reusable source foundation, not autonomous production.
The founder approved an exact-merge successor mandate at `2026-09-27T19:22:51Z`.
Its intelligence, hypothesis and representation invocations succeeded. Three earlier
strategy revisions remain rejected evidence; replacement campaign
`8e68ee6b-0807-4e67-8268-55313b89dd7e` used the corrected native commit and completed
independent review plus a terminal mixed-basket BT-009 publication. No old mandate,
approval or failed campaign was retroactively broadened.

The next production cycle demonstrated the intended reasoning boundary. Exact recent
candidate questions were supplied as novelty exclusions, while a rotating catalog
frontier supplied underexplored starting points without compelling artificial asset
diversity. The senior researcher proposed SOL-to-ETH, RUNE and XAUT/PAXG mechanisms.
The representation scientist retained two mixed baskets where both legs were causal,
kept RUNE single-asset where another asset was unnecessary, selected 2h/4h complete
bars, and rejected fractional differentiation rather than applying it decoratively.
Deterministic DATA gates then rejected XAUT/PAXG for unavailable evidence and admitted
the other panels. Native Bulletproof then evaluated the preregistered SOLUSDT-to-
ETHUSDT question over 2023 and retained a negative result: 41 supporting observations,
mean net signed residual return `-0.0012288419031189024`, and doubled-cost mean
`-0.0021288419031189024`. Receipt
`0ba464c8a583ababfa81b8ddbc5b7e424302befdfda1d529947a9e392a5268bc` was published
through complete BT-009 bridge `56341390-6d9c-5f9b-8ab3-71e2ccf93a9f`; no LLM
calculated those metrics or decided the gates. The controller retained the failure and
automatically drafted the next RUNEUSDT question, stopping at explicit new-code
approval task `A3-8e68ee6b-002-G3`. This demonstrates proposal, representation,
native evaluation and non-idle queue progression without giving an LLM approval,
promotion, shadow, order or capital authority.

Signed producer receipts must be registered through the native Python/bootstrap path
without reconstructing their JSON through `jq`; numeric reserialization changes the
content digest and must fail closed. That is an evidence-integrity invariant, not an
operator workaround.

On 2026-09-30 the current reasoning contract entered production under canonical weekly
mandate `dc0784e3-a778-4f8c-b6ae-41a3f5d79906`, digest `29f0403d...a03`.
It exposes 120 DATA-002 catalog-visible instruments, permits a reasoned proposal of up
to 100 members, binds the latest complete one-year window ending
`2026-08-08T20:14:00Z`, and carries 50 native mechanism capabilities from exact
Bulletproof commit `dc72d86...d552`. The underlying BTC admission explicitly includes
CSI component, readiness, source, raw, percentile and bucket fields. Six legacy weekly
mandates were superseded and one canonical mandate remained active. This proves the
reasoning context and governance boundary are deployed; it does not prove that an LLM's
asset choice, representation choice or mechanism proposal is economically correct.

RI-017's same-day production manifest is `qualified` for every configured connector
class: scholarly indexes, Atom/RSS, an official transcript feed, exact-DID public-social
observations and official YouTube metadata. Those receipts broaden question-generation
evidence but remain quarantined source material. They grant no equation, alpha,
promotion, order or capital authority.
