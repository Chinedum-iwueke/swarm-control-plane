# Invariance Trading Firm Operating Alignment

**Status:** Governing alignment for Hermes work after M9  
**Source:** `Invariance_Agentic_Systematic_Trading_Firm_PRD.pdf`, version 1.0,
31 July 2026  
**Scope:** The shortest path from the current platform to a useful daily research
institution

## Governing Outcome

Hermes exists to build a closed, auditable systematic-research institution. Its
advantage is not one model or one agent. It is the ability to discover predictive
relationships, reject false ones cheaply, retain every result, construct portfolios
from independently validated signals, validate implementation prospectively, and
deploy only through deterministic risk controls.

This makes the trading-firm PRD the product authority for research, portfolio, and
trading capabilities. The Hermes system design remains the authority for machine
boundaries and secure execution. When plans conflict, work must preserve both the
PRD's scientific gates and Hermes's least-privilege controls.

## What The PRD Changes

The next objective is not to instantiate 52 continuously running agents. The 52
entries are governed specialist profiles that can be activated per task. The PRD
itself makes the **RI-4 closed five-agent research loop** the first operational
research team:

1. **Senior Quantitative Research Specialist** creates a cited research brief,
   prior-art map, assumptions register, and falsifiable hypothesis. It has read-only
   research access and cannot execute, approve, deploy, or trade.
2. **Experiment Specification Agent** converts an approved registered hypothesis
   into a locked manifest covering data, features, labels, splits, purging, embargo,
   controls, costs, stresses, trial budget, success criteria, and failure criteria.
   It cannot inspect results before the specification is locked.
3. **Research Execution Agent** executes the approved manifest through
   `bulletproof_bt` in an isolated workspace and preserves code, data, configuration,
   logs, checksums, and results. It cannot alter the hypothesis, engine, data, costs,
   or validation plan.
4. **Statistical Reviewer** independently reproduces and evaluates the result using
   trial-aware methods. It cannot redesign a failed hypothesis or approve live
   capital.
5. **Adversarial Research Auditor** attempts to disprove the claim through competing
   explanations, hidden-beta tests, benchmark attacks, alternate definitions, and
   economic criticism. It cannot modify the candidate or omit contrary evidence.

The existing `vm1-research-runner` is an execution capability, not this full loop.
M8 proved isolated deterministic execution, basic out-of-sample evaluation, cost and
lag stress, evidence hashing, and a bounded audit on synthetic data. It did not prove
research intelligence, immutable trial registration, independent reproduction,
point-in-time market data, sealed holdouts, full trial-aware statistics, or
prospective performance.

## Required Shared Services

The first five profiles should be thin, replaceable reasoning and execution roles
over shared institutional services. Build these in the PRD's order:

1. **RI-1 Research Knowledge Foundation:** source ingestion, metadata, hybrid search,
   exact passage retrieval, citations, prior experiment retrieval, and retrieval
   evaluation.
2. **RI-2 Research Intelligence:** cited synthesis, prior-art comparison, structured
   hypothesis generation, method recommendations, assumptions, and failure
   conditions.
3. **RI-3 Trial Registry and Experiment Contracts:** immutable hypothesis and
   experiment manifests, global trial IDs, family counts, dataset and code lineage,
   negative results, reviews, and decisions.
4. **RI-4 Closed Five-Agent Loop:** independently permissioned proposal,
   specification, execution, statistical review, and adversarial review with founder
   approval before execution.

ADL factor mining, broad autonomous search, portfolio construction, shadow trading,
micro-live execution, and production trading follow these foundations. Building them
earlier would automate selection bias rather than research.

## Daily Discovery Loop

The initial daily process should be scheduled but bounded. It should not search
continuously without a registered mandate.

### Morning: learn and propose

1. The Research Program Director selects one bounded question from founder
   priorities, portfolio gaps, literature, prior failures, or unexplained evidence.
2. The Senior Specialist retrieves cited sources and related Invariance trials.
3. It emits one atomic hypothesis with mechanism, universe, target, horizon, null,
   expected effect, data needs, cost sensitivity, and explicit failure conditions.
4. The registry rejects duplicates or records the relationship to an existing trial
   family.

### Midday: register and execute

1. The Experiment Specification Agent creates a locked, machine-readable manifest.
2. The founder approves the manifest digest, not an open-ended instruction.
3. The Research Execution Agent runs `bulletproof_bt` against a versioned data
   snapshot and pinned repository commit.
4. All variants, failures, resource use, logs, and artifacts are registered. A
   technically failed or negative experiment is still a completed research record.

### Afternoon: falsify and decide

1. The Statistical Reviewer reproduces the run in a clean workspace and evaluates
   effect size, dependence, effective sample size, purging, embargo, bootstrap,
   selection adjustment, parameter stability, and net economics.
2. The Adversarial Auditor attacks leakage, hidden beta, benchmark equivalence,
   narrow periods, fragile costs, alternate universes, and competing mechanisms.
3. The system records `rejected`, `revise`, or the next promotion state with dissent
   and limitations. No research result becomes live-trading authority.
4. A founder digest reports what was learned, what was rejected, what remains
   uncertain, and the best next question.

## First Useful Operating Scope

Start with one research question per day and one active trial family at a time. Use
human-observation-led, literature-led, and institutional-memory-led discovery first.
These modes produce interpretable, attributable hypotheses without requiring an
autonomous factor DSL or broad search budget.

The first real `bulletproof_bt` pilot should use an approved, immutable historical
dataset snapshot and answer one signal-level question. It must test predictive
information before optimizing entries, exits, sizing, or a complete strategy. The
result must include a simple baseline, realistic costs, purged time-aware validation,
and an independent review.

Do not enable daily unattended research until the registry can count every attempted
variant and retain negative results. Otherwise repeated automation creates invisible
multiple testing.

## Immediate Build Sequence

### M10: Research contracts and registry

- Define source, hypothesis, experiment, trial, result, review, and decision schemas.
- Add immutable lineage from hypothesis through dataset snapshot, code commit,
  manifest, run output, and reviews.
- Track trial families and all attempted variants, including failures.
- Expose proposal and review states in Mission Control and Telegram without making
  Telegram a free-form execution boundary.
- Exit when a hypothesis and locked manifest can be registered, approved by digest,
  executed once, reviewed independently, and retained regardless of outcome.

### M11: Research knowledge foundation

- Ingest the PRD, selected statistics and time-series texts, chosen papers, and prior
  Invariance reports with page/section metadata.
- Implement hybrid retrieval with exact citations and evidence classification.
- Add similar-hypothesis and prior-failure retrieval.
- Evaluate retrieval on a fixed question set before allowing it to propose research.
- Exit when one question produces a traceable brief whose material claims resolve to
  source passages or are labeled as agent inference.

### M12: Closed five-agent pilot

- Register five separate role packages and permission profiles.
- Require separation between proposer, executor, statistical reviewer, and
  adversarial auditor; the specification role cannot inspect unlocked results.
- Adapt `bulletproof_bt` behind a registered experiment contract and immutable data
  snapshot interface.
- Run one real-data, non-live signal experiment end to end with founder approval.
- Exit when the complete positive or negative trial is reproducible and searchable.

### M13: Daily supervised research

- Add one-question-per-day scheduling, compute and trial budgets, duplicate checks,
  daily digest, and weekly research-program review.
- Measure cheap-falsification rate, time to registered experiment, reproduction rate,
  trial-adjusted survivor rate, duplicate work avoided, and negative-result retention.
- Exit after a multi-week run produces complete records without gate bypasses or
  terminal babysitting.

## Non-Negotiable Gates

- Register before observing results.
- Research signals before constructing strategies.
- Count all trials and retain all negative results.
- Pin data, code, configuration, costs, and validation before execution.
- Keep proposer, executor, validator, and promotion authority separate.
- Hide sealed-holdout detail from exploratory agents.
- Prefer broad stable plateaus and net economics over peak historical metrics.
- Require shadow and micro-live evidence before production eligibility.
- Keep prop-firm constraints as a portfolio overlay, not an alpha objective.
- Let deterministic code, not language models, control orders, accounting, risk,
  reconciliation, approvals, and secrets.
- Require human approval for research mandates, live promotion, risk limits, capital
  scaling, and material architecture changes.

## Founder Interaction

Plain English remains the founder interface. A planning role may translate a request
such as "investigate whether funding extremes predict short-horizon residual returns"
into a draft research brief and hypothesis. The founder reviews the rationale,
evidence, limits, and proposed budget, then approves the immutable hypothesis or
experiment digest. Approval never authorizes unspecified commands, scope expansion,
live deployment, or capital.

Mission Control should show the active research question, stage, owner profile,
lineage, trial-family count, compute budget, evidence grade, dissent, next gate, and
all rejected results. Telegram should notify and deep-link to the same bounded review;
it should not accept passwords, secrets, arbitrary shell commands, or unscoped risk
changes.

## Definition Of Being Off And Running

Invariance is operationally researching when the founder can pose one plain-English
question and receive, without terminal intervention:

1. a cited brief and nonduplicate registered hypothesis;
2. a locked, approved experiment manifest;
3. an isolated `bulletproof_bt` execution against pinned data and code;
4. independent statistical reproduction and adversarial criticism;
5. a searchable accepted, rejected, or revise decision with complete lineage; and
6. a daily digest that proposes the next bounded question.

That is the first useful institution. The remaining specialist profiles are activated
only when this loop creates a demonstrated need for their distinct responsibility and
permission boundary.
