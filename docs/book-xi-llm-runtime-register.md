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
| Data representation scientist | `AlphaDiscoveryExecutor`, stage `representation` | Selects pre-outcome baskets, member roles, clocks and a typed transformation graph; may use or cross optional stable/volatile labels when justified; records rejected alternatives | `adaptive-representation-plan-v1.0.0` only | Catalog-label validation, exact DATA-002/003 panel admission, native causal replay, exact strategy-consumer binding and terminal BT-009 evidence |
| Strategy engineer | `EngineeringMissionExecutor`, coding session | Drafts an exact native Bulletproof hypothesis contract, strategy and tests in an isolated worktree | Approved paths and diff budget only | Tests, independent review, PR/merge and source-commit rebinding |
| Engineering reviewer | `EngineeringMissionExecutor`, review session | Reviews the uncommitted engineering patch against its immutable acceptance contract | Read-only | High findings fail the task; it cannot merge or approve itself |
| Strategy-spec reviewer | `AlphaStrategyReviewExecutor` | Independently critiques native strategy/spec equivalence and reproducibility | Structured review only | Separate evaluator profile and controller reconciliation |
| Causality/leakage reviewer | `AlphaStrategyReviewExecutor` | Independently checks timing, leakage, target and implementation equivalence | Structured review only | Separate evaluator profile and controller reconciliation |
| PDF recovery adviser | `backend/app/ingestion/recovery_controller.py` | Classifies bounded ingestion failures and proposes recovery actions | Recovery recommendation only | Deterministic sanitizer/parser policy; no canonical overwrite |
| Mission Control research copilot | `mission-control/src/hermes_mission_control/research_copilot.py` | Explains visible research evidence to the founder | UI response only | No task, approval, capital or order authority |

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

## Evidence requirements

Every invocation binds a source commit, role package, model/runtime identity, task
contract and retained output. Agent reasoning must be replayable from supplied context.
Scientific equations require deterministic or genuinely independent assurance; an LLM
cannot verify its own transcription. Failed, rejected and invalid outputs remain part of
institutional memory and novelty scoring.
