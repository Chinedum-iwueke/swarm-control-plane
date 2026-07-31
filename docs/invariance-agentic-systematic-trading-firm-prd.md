# Invariance Research: Agentic Systematic Trading Firm PRD

> Machine-readable transcription of `Invariance_Agentic_Systematic_Trading_Firm_PRD.pdf`.
> The PDF remains the canonical visual source. This transcription exists for search,
> retrieval, agent context, version control, and citation by section.
> Source PDF SHA-256:
> `58d120ddcfc1865c5d8868aedb6dfc64d96533f4b9ad332b0cd20f6f30554846`.

INVARIANCE RESEARCH
Agentic Systematic Trading Firm
Product Requirements Document
The 52-Agent Architecture for Continuous Discovery, Falsification, Portfolio Construction,
Deployment, and Learning
## North-star mandate
Build a closed research institution that continuously discovers predictive relationships, attempts to falsify them, converts
survivors into portfolio-ready signals, validates implementation prospectively, deploys under deterministic risk controls,
measures live degradation, and compounds institutional knowledge.
Document owner: Founder / Chief Investment Officer
Product scope: Bulletproof BT, Hermes Research Swarm, Research Intelligence Service, Autonomous Alpha
Discovery Laboratory, Portfolio and Production Control Plane
Status: Foundational PRD for phased implementation
Version: 1.0 | Date: 31 July 2026
## Document Control
Purpose Define the company-wide agent architecture, operating loop,
discovery modes, governance, system requirements, interfaces,
permissions, deployment topology, and phased build plan.
Primary users Founder/CIO, future human team members, Hermes agents,
quantitative researchers, developers, risk operators, data
engineers, and auditors.
Binding effect This document defines the target operating model. Individual
implementations may evolve, but no component may bypass
the promotion state machine, trial registry, independent
validation, or deterministic risk controls.
Supersedes Standalone strategy-tester mentality and any agent design that
allows one agent to propose, test, approve, deploy, and judge
its own work.
Review cadence Quarterly architecture review; immediate review after any
material live incident, major data-source change, new asset
class, or modification to promotion criteria.
## Executive Summary
Invariance Research is being designed as a systematic trading firm whose primary competitive advantage is
not a single strategy, model, or agent. Its advantage is a governed process for searching more intelligently,
falsifying more aggressively, learning cumulatively, and deploying more safely than an informal trading
operation.
The product described in this PRD combines Bulletproof BT, a Research Intelligence Service, a 52-profile
Hermes swarm, a constrained Autonomous Alpha Discovery Laboratory, portfolio construction services,
shadow and micro-live validation, deterministic execution and risk controls, and a durable institutional
memory. Together they implement a continuous loop:
LEARN -> OBSERVE -> PROPOSE -> REGISTER -> FORMALIZE -> TEST -> FALSIFY
-> COMBINE -> SHADOW -> MICRO-LIVE -> MEASURE DEGRADATION
-> RETAIN / MODIFY / RETIRE -> LEARN AGAIN
The system is explicitly not a “smart trader” that is told to find money. It is an autonomous scientific discovery
institution. Agents receive almost no credit for spectacular in-sample performance. They are rewarded for
producing effects that survive unseen periods, unseen instruments, realistic execution, alternative datasets,
perturbations, independent criticism, portfolio tests, prospective observation, and live implementation.
- Bulletproof BT becomes an alpha-research and portfolio-validation platform, not only a strategy backtester.
- Signal discovery is separated from trade-rule construction, portfolio admission, and deployment.
- Every hypothesis, model variation, parameter combination, dataset, code revision, and outcome is
registered before results are interpreted.
- Machine learning is used first for conditional trade quality, meta-labelling, regime conditioning, cost and
fill prediction, volatility, expected return, and strategy selection - not naive next-bar direction.
- Autonomous search is constrained by a point-in-time-safe research API, a feature/alpha domain-specific
language, immutable holdouts, trial-aware statistics, compute budgets, and adversarial evaluation.
- Prop-firm constraints are implemented as a separate portfolio-risk overlay rather than embedded into
alpha discovery.
- Production promotion follows a mandatory state machine from proposed to screened, replicated, robust,
shadow, micro-live, portfolio-eligible, production, degraded, and retired.
- No Hermes agent can independently increase risk, access hidden holdouts, modify canonical data, alter the
execution engine, or deploy unapproved strategies.
## Contents
## 1. Product Vision and Objectives
## 2. Operating Principles and Non-Negotiables
## 3. Systematic Trading Production Loop
## 4. Research Intelligence Layer
## 5. Autonomous Alpha Discovery Laboratory
## 6. Discovery Modes
## 7. Machine Learning Product Roadmap
## 8. Product Architecture and Core Services
## 9. The 52-Agent Operating Model
## 10. Permissions, Governance, and Decision Rights
## 11. Data, Metadata, and Experiment Contracts
## 12. Promotion State Machine and Stage Gates
## 13. Deployment Topology
## 14. Phased Delivery Roadmap
## 15. Metrics and Acceptance Criteria
## 16. Risks, Failure Modes, and Guardrails
## 17. Appendices
## 1. Product Vision and Objectives
### 1.1 Product vision
Create an agentic systematic trading firm that compounds process knowledge. The firm must be able to
discover weak but repeatable predictive relationships, distinguish genuine effects from machine-scale false
discovery, combine independent signals into portfolios, validate implementation prospectively, deploy through
deterministic controls, and learn from the difference between expected and realized behavior.
### 1.2 Primary objectives
1. Convert Bulletproof BT from a strategy tester into an alpha-research and portfolio-validation platform.
2. Separate signal discovery, strategy construction, portfolio construction, execution, risk, and live learning
into governed services and agent roles.
3. Create a shared Research Intelligence Service combining foundational knowledge, current literature, and
Invariance Research memory.
4. Enable bounded autonomous discovery over interpretable feature and signal spaces without granting
agents unrestricted access to code, data, or holdouts.
5. Introduce machine learning immediately where it improves conditional decisions under costs.
6. Create a trial-aware research process that records failures and adjusts for selection.
7. Build shadow and micro-live stages that validate implementation before material capital is at risk.
8. Maintain a separate prop-firm overlay capable of evaluating pass probability, breach probability, and
funded-account survival.
9. Establish strict human and agent decision rights, with deterministic pre-trade and real-time risk
enforcement.
10. Measure live degradation and use it to improve research, portfolio, execution, and monitoring methods.
### 1.3 Non-goals
- Guaranteeing profitable alpha or future returns.
- Building a single omnipotent agent with unrestricted access.
- Using historical profit as the primary reward for autonomous research.
- Training a custom model on every book before a traceable retrieval system exists.
- Allowing online agents to rewrite strategies and trade newly discovered anomalies immediately.
- Using deep reinforcement learning as the first discovery method.
- Optimizing solely for prop-firm challenge rules or one provider’s current commercial terms.
- Replacing deterministic order, accounting, reconciliation, or risk controls with free-form language-model
reasoning.
## 2. Operating Principles and Non-Negotiables
Scientific before profitable
The system searches for defensible predictive relationships and survival through falsification gates. Historical profitability is
evidence, not proof.
Register before observing
Every hypothesis and candidate specification must be recorded before results are observed. Unregistered results cannot enter
the signal library.
Signals before strategies
Research first asks whether information predicts a target. Entry, exit, sizing, and execution wrappers are designed only after
predictive content is established.
Broad plateaus over isolated peaks
Stable effects across neighboring parameters, assets, periods, and definitions are preferred over exceptional configurations.
Net economics over model metrics
Net expected value after Tier-2 and Tier-3 cost assumptions is the governing score; accuracy, AUC, and gross Sharpe are
secondary diagnostics.
Institutional memory is an asset
Negative results, rejected ideas, failed replications, and live degradation are retained and retrievable.
Independent judgment
Proposers cannot approve their own experiments, validators cannot modify the tested strategy, deployment cannot alter
approved logic, and risk can stop but not increase exposure.
Prospective evidence matters
Shadow and micro-live observation are required because historical data cannot fully represent execution, market adaptation,
and operational reality.
Complexity pays rent
Additional features, model classes, conditions, and parameters must produce measurable incremental value after selection
penalties.
Humans remain accountable
Agents prepare, execute, critique, and monitor. Human owners approve research mandates, risk limits, live promotion, capital
scaling, and material architectural changes.
## 3. Systematic Trading Production Loop
### 3.1 Closed-loop architecture
FOUNDATIONAL KNOWLEDGE + CURRENT LITERATURE + INVARIANCE MEMORY
|
v
RESEARCH INTELLIGENCE
|
v
OBSERVE -> PROPOSE -> REGISTER -> FORMALIZE -> SCREEN -> VALIDATE
^ |
| v
LEARN <- RETIRE / MODIFY / RETAIN <- LIVE DEGRADATION <- SHADOW
^ |
| v
POST-TRADE ATTRIBUTION <- PRODUCTION <- MICRO-LIVE <- PORTFOLIO
### 3.2 Production-loop stages
Stage Purpose Mandatory exit artifact
Learn and observe Retrieve literature, prior experiments,
failure patterns, live anomalies, portfolio
weaknesses, and execution evidence.
Research brief
Propose Generate atomic predictive hypotheses
with mechanism, target, horizon,
expected effect, and falsification
conditions.
Hypothesis object
Register Create immutable hypothesis and
experiment records, trial-family counts,
data snapshot, code commit, and planned
validation.
Registry record
Formalize Translate the hypothesis into a machine-
readable experiment specification using
approved features and targets.
Experiment specification
Screen Run low-cost diagnostic tests designed to
reject most candidates quickly.
Screening report
Validate Use purged walk-forward evaluation,
embargo, alternate universes, stress,
selection adjustment, replication, and
adversarial criticism.
Independent validation package
Construct Design trade rules only for validated
signals; estimate costs, MFE/MAE, holding
period, and execution alternatives.
Strategy specification
Combine Evaluate marginal contribution,
correlation, capacity, turnover, and risk
within the signal and strategy library.
Portfolio contribution report
Shadow Generate live predictions and
hypothetical orders without capital.
Measure data, timing, costs, fills, and
forecast calibration.
Prospective validation report
Micro-live Use minimal capital to validate order
state, reconciliation, risk controls, actual
costs, and implementation parity.
Implementation validation report
Production and scale Allocate only after live degradation is
measured and acceptable. Scaling is
conditional and reversible.
Capital allocation decision
Learn again Feed outcomes, failures, drift, incidents,
and live degradation back into the
Research Intelligence Service and trial
registry.
Updated institutional memory
### 3.3 Feedback loops
- Research feedback: failed and successful results update similar-hypothesis retrieval and method
recommendations.
- Execution feedback: predicted versus realized costs update cost models and trade gating.
- Portfolio feedback: correlation, concentration, and marginal contribution shape future research priorities.
- Risk feedback: drawdowns, breaches, and scenario failures alter limits and candidate acceptance criteria.
- Production feedback: live degradation separates research error, implementation error, regime change, and
data error.
- Organizational feedback: agent-quality metrics alter prompts, permissions, review requirements, and task
routing.
## 4. Research Intelligence Layer
### 4.1 Position in the pipeline
BOOKS / PAPERS / NOTES / PRIOR EXPERIMENTS
|
v
RESEARCH KNOWLEDGE SYSTEM
|
v
SENIOR QUANTITATIVE RESEARCH SPECIALIST
|
v
FORMAL HYPOTHESIS SPECIFICATION
|
v
EXPERIMENT SPECIFICATION AGENT
|
v
BULLETPROOF BT RUNNER
|
v
STATISTICAL REVIEW -> ADVERSARIAL AUDIT
|
v
TRIAL REGISTRY AND MEMORY
+--------------------> RESEARCH INTELLIGENCE
The Research Intelligence Layer is built before the entire production swarm is complete. It sits between
research data and experiment execution. It does not begin as a smart trader. It begins as a research reasoning
system that can retrieve knowledge, inspect prior work, propose mathematically defensible hypotheses, and
generate structured specifications for Bulletproof BT.
### 4.2 Five intelligence types
Domain knowledge
Probability, mathematical statistics, stochastic processes, time-series analysis, econometrics, optimization, information theory,
machine learning, market microstructure, behavioral finance, portfolio construction, execution, transaction costs, risk,
derivatives, futures, and empirical asset pricing.
Institutional memory
Every hypothesis, trial, dataset, parameter grid, failure, selected configuration, robustness result, shadow observation, live
degradation report, note, and methodological decision.
Mathematical reasoning
Methods, dependence, non-stationarity, estimators, assumptions, nulls, sample size, leakage, multiple testing, economic
significance, and falsification.
Market context
Instrument, horizon, liquidity, fees, slippage, funding, volatility, exchange constraints, latency, leverage, and liquidation
mechanics.
Scientific discipline
Every proposal must state rationale, target, features, data requirements, null, expected effect, failure conditions, validation,
cost assumptions, selection adjustment, and deployment implications.
### 4.3 Retrieval architecture
SOURCE DOCUMENTS -> PARSER -> CHUNKING + METADATA -> HYBRID INDEX
-> RESEARCH RETRIEVAL SERVICE -> GENERAL REASONING MODEL
-> STRUCTURED, CITED RESEARCH OUTPUT
The initial implementation uses retrieval-augmented generation rather than attempting to train a model to
memorize all books and papers. Every material research claim must remain traceable to source, page, section,
experiment record, or explicit agent inference.
### 4.4 Knowledge collections
- Foundational Knowledge: mathematics, statistics, econometrics, machine learning, optimization, finance,
and market microstructure.
- Current Research Literature: academic papers, working papers, practitioner research, conference
publications, and exchange documentation.
- Invariance Research Memory: Bulletproof BT experiments, notebooks, hypotheses, rejected ideas, strategy
specifications, validation reports, cost studies, shadow results, and live degradation.
### 4.5 Research Intelligence Service APIs
POST /v1/research/search
GET /v1/research/sources/{source_id}
POST /v1/research/similar-hypotheses
POST /v1/research/methods/recommend
POST /v1/research/experiments/search
POST /v1/research/hypotheses
POST /v1/research/reviews
POST /v1/research/conclusions
### 4.6 Evidence classification
- Established mathematical result
- Empirical finding
- Author interpretation
- Market-specific evidence
- Invariance Research evidence
- Agent inference
Every conclusion must identify its evidence category. Retrieved material is not automatically true, applicable,
current, replicable, or economically meaningful.
## 5. Autonomous Alpha Discovery Laboratory
### 5.1 Correct mandate
Prohibited objective
Find a statistical pattern that will surely give us an edge.
Required objective
Discover predictive relationships that survive unseen markets, unseen periods, realistic execution, alternative datasets,
perturbations, competing hypotheses, prospective observation, and trial-aware statistical scrutiny.
An agent rewarded for finding a sure edge may exploit leakage, timestamps, simulator flaws, excessive search,
lucky holdouts, hidden tail risk, or unrealistic fills. The laboratory must therefore reward survival through
falsification, not historical profit alone.
### 5.2 Discovery score
Discovery Score = P(effect is real) x P(effect persists) x economic magnitude x capacity
- cost - complexity - selection penalty
R = w1*OOS_IC + w2*OOS_EV + w3*Stability + w4*CrossMarket
+ w5*CostSurvival - w6*Drawdown - w7*Turnover - w8*Complexity
- w9*TrialPenalty - w10*RegimeConcentration
### 5.3 Market laboratory
- Versioned OHLCV, trades, order books where available, funding, open interest, liquidations, basis, spreads,
depth, cross-asset prices, exchange state, time variables, liquidity and volatility regimes, benchmark assets,
and known protocol or corporate events.
- Point-in-time-safe API access rather than unrestricted database access.
- Delayed availability, survivorship and delisting handling, immutable partitions, query logging, feature
lineage, and sealed holdouts.
- No direct agent access to hidden validation files.
### 5.4 Constrained alpha language
Initial autonomous discovery uses a constrained symbolic language rather than arbitrary Python. The DSL
supports lags, differences, returns, rolling statistics, ranks, z-scores, correlations, residuals, quantiles, entropy,
acceleration, cross-sectional dispersion, volatility scaling, interactions, conditional operators, neutralization,
and regime gates.
signal:
expression:
multiply:
- rank:
input: {rolling_zscore: {input: funding_rate, window: 72}}
- negate:
rank:
input: {return: {horizon: 12}}
universe: {liquidity_rank_max: 30}
holding_period: {bars: 6}
neutralization: {market_beta: true, volatility: true}
### 5.5 Search scheduler
11. Test a large candidate set using inexpensive screening.
12. Retain a small fraction using predeclared filters.
13. Expand periods, instruments, costs, and controls.
14. Run full walk-forward and trial-aware evaluation.
15. Adversarially test the survivors.
16. Shadow only a small number of candidates.
17. Promote to micro-live only after implementation readiness.
### 5.6 Research self-play analogues
Researcher versus Critic
Explorer earns reward when a signal survives independent validation. Critic earns reward for exposing leakage, instability,
execution flaws, or hidden concentration.
Strategy versus Market Adversary
A stress agent changes plausible spreads, latency, volatility, liquidity, correlation, funding, gaps, and fill probability to expose
fragility.
Current model versus archived models
A synthetic league tests policies against mixtures of earlier policies and participant types. It is a robustness laboratory, not
proof of real-market profitability.
Researcher versus Red Team
The Red Team attempts to infer holdouts, exploit caches, alter costs, submit invalid values, exploit bar boundaries, or overwrite
outputs. The system must detect and block these behaviors.
## 6. Discovery Modes
### 6.1 Mode A - Literature-led hypothesis discovery
The Senior Quantitative Research Specialist retrieves mathematical and empirical literature, compares it with
prior Invariance evidence, and proposes a pre-registered atomic hypothesis.
### 6.2 Mode B - Institutional-memory-led discovery
The system mines failures, partial successes, live degradation, execution errors, and unresolved research
questions to identify nonredundant follow-up studies.
### 6.3 Mode C - Human-observation-led discovery
A founder or researcher records a market observation. The system converts it into a falsifiable claim and
searches for related prior work before any test runs.
### 6.4 Mode D - Autonomous factor mining
Symbolic regression, genetic programming, Bayesian optimization, random grammar search, gradient-guided
factor generation, and LLM-guided composition search interpretable candidate factors within the DSL.
### 6.5 Mode E - Cross-sectional and cross-market discovery
Agents search rankings, residual returns, relative-value relationships, cross-exchange lead-lag, carry, basis,
funding, dispersion, and cross-asset conditioning. Replication across markets helps distinguish universal
mechanisms from crypto-specific artifacts.
### 6.6 Mode F - Event and microstructure discovery
Agents study liquidations, order-flow pressure, spread behavior, funding resets, volatility shocks, depth
changes, abnormal volume, and exchange-specific events.
### 6.7 Mode G - ML-assisted conditional discovery
ML identifies when a known signal is likely to work, fail, become expensive, or become dangerous. The output
is conditional trade quality, expected return, risk, cost, or survivability - not generic directional prediction.
### 6.8 Mode H - Researcher-critic adversarial league
Explorer, experiment designer, statistical auditor, falsifier, and research governor form a bounded scientific
game. The objective is fast rejection of false edges and durable retention of survivors.
### 6.9 Mode I - Synthetic multi-agent market laboratory
Noise traders, market makers, trend followers, mean reverters, liquidators, arbitrageurs, informed agents, and
archived policies create plausible counterfactual environments. Results remain hypotheses until validated
against historical and prospective real data.
### 6.10 Mode J - Prospective shadow discovery
Live observation can identify anomalies and distribution shifts, but newly discovered effects cannot be traded
immediately. They return to the research pipeline for registration, testing, and governance.
## 7. Machine Learning Product Roadmap
### 7.1 Assumptions to kill
Incorrect assumption Required replacement
ML predicts returns. ML predicts conditional trade quality, risk, costs, fill
probability, expected return, and survivability under costs.
More features help. Every feature must be timestamp-provable, economically
interpretable or empirically justified, versioned, and leakage-
audited.
Offline accuracy matters. Net expected value under realistic Tier-2 and Tier-3
assumptions is the governing score.
Large row counts mean large samples. Effective sample size must account for overlap, common
exposure, dependence, regime concentration, and repeated
events.
A more complex model is better. The complex model must beat transparent baselines after
costs, uncertainty, and selection penalties.
### 7.2 Reality-aligned labels
- Barrier/event label: Did the opportunity reach +aR before -bR within horizon H?
- Every label stores label_end_time to enable purging and embargo.
- Additional targets: forward residual return, volatility, MFE, MAE, fill probability, slippage, continuation
probability, and drawdown contribution.
- Labels must match the actual decision the model will control.
### 7.3 Initial decision roles
- Enter or skip
- Size up or down within deterministic limits
- Select among approved strategies
- Condition a signal on regime
- Estimate cost and fill quality
- Estimate expected return and uncertainty
- Forecast volatility and correlation
### 7.4 Model sequence
18. Create transparent baselines: logistic regression, regularized linear models, simple thresholds, and
calibrated scorecards.
19. Add gradient boosting, random forests, generalized additive models, and other moderate-complexity
models.
20. Use neural methods only where sample structure, data quality, and incremental value justify them.
21. Use offline reinforcement learning downstream of a validated signal library for act/skip, allocation,
inventory, combination, and exit decisions.
22. Use synthetic multi-agent environments for robustness learning, never as sole evidence of real-market
profitability.
### 7.5 ML acceptance criteria
- Improves net out-of-sample expected value, risk, cost, or portfolio contribution versus the approved
baseline.
- Remains calibrated prospectively.
- Survives purged walk-forward validation, embargo, drift tests, and alternate samples.
- Has documented feature availability and model lineage.
- Fails safely when inputs are missing, stale, shifted, or outside training support.
- Can be paused or replaced without disabling deterministic risk controls.
## 8. Product Architecture and Core Services
### 8.1 Logical architecture
RESEARCH INTERFACES (Mac / Dashboard / Telegram)
|
v
SWARM CONTROL PLANE + APPROVALS
|
+---------------+-------------------+
| | |
RESEARCH VALIDATION PRODUCTION
INTELLIGENCE SERVICES SERVICES
| | |
+-------> BULLETPROOF BT <-----------+
|
PORTFOLIO + RISK ENGINE
|
EXECUTION + RECONCILIATION
|
EXCHANGES / BROKERS / PROP ACCOUNTS
Shared foundations: PostgreSQL/pgvector, artifact store, logs, metrics, secrets, versioned data
### 8.2 Required core services
Service Requirement
Research Intelligence Service Hybrid retrieval, citations, methods, prior experiments, similar
hypotheses, conclusions.
Research Registry Hypotheses, experiments, trials, results, relationships, failures,
and decisions.
Market Research API Point-in-time-safe data access with logged queries and
immutable snapshots.
Feature and Alpha DSL Compiler Validates symbolic expressions and compiles them into causal
feature pipelines.
Experiment Orchestrator Runs registered jobs, enforces manifests, compute budgets,
retries, and artifact capture.
Statistical Evaluation Service Purging, embargo, bootstrap, DSR, PBO, multiple-testing
correction, effective sample size, and stability.
Adversarial Validation Service Stress, placebo, alternate universe, timestamp shift, outlier
removal, and simulator-exploit tests.
Signal Library Versioned approved signals, forecast calibration, status,
lineage, and expected scope.
Portfolio Construction Service Forecast normalization, allocation, constraints, turnover,
capacity, and marginal contribution.
Prop-Firm Overlay Service Firm-specific account rules, breach simulation, pass
probability, and survival analytics.
Shadow Market Service Live features, predictions, hypothetical orders, observable fills,
latency, and prospective outcomes.
Execution and OMS Deterministic order generation, state management, duplicate
prevention, retries, and acknowledgements.
Pre-Trade and Real-Time Risk Deterministic limits, stale-data controls, exposure, drawdown,
halts, and kill switches.
Reconciliation Service Independent comparison of internal and external positions,
orders, balances, and fills.
Observability and Incident Service Logs, metrics, traces, alerts, incidents, runbooks, and
postmortems.
Artifact and Lineage Service Immutable references to data, code, configuration, reports,
models, containers, and decisions.
## 9. The 52-Agent Operating Model
The architecture contains exactly 52 governed agent profiles. They are reusable specialist roles, not necessarily
52 continuously running processes. The control plane instantiates profiles per task, applies least privilege,
records every action, and routes outputs to independent reviewers.
Senior research specialist profile
The principal research-intelligence agent is intentionally specified as a computer-native polymath with doctoral-level
competence across statistics, mathematics, physics, computer science, and econometrics simultaneously, plus time-series
research, ML validation, portfolio construction, market microstructure, independent research, scientific writing, and
reproducible computation. This describes the capability envelope expected from the agent, not a realistic requirement for one
human hire.
### 1. Research Program Director Agent
Division: Executive Coordination
Coordinates the research agenda and converts firm priorities into bounded programs.
Core responsibilities Maintain backlog; group hypotheses; allocate compute; prevent
duplication; track dependencies; surface portfolio gaps.
Required outputs Program charter; ranked backlog; weekly plan; budget
recommendation; escalation report.
Permissions and prohibitions May create and assign research tasks; may not approve
promotion, alter live risk, or trade.
Activation triggers New CIO directive; weekly planning; portfolio gap; failed
program.
Key dependencies Research Registry; Portfolio Analyst; CIO.
Success measures Research throughput, duplicate work avoided, value of
information per compute unit.
### 2. Investment Committee Secretary Agent
Division: Executive Coordination
Builds complete evidence packages and preserves the decision record.
Core responsibilities Collect artifacts; verify gates; summarize dissent; create
approval memo; track conditions and expiry.
Required outputs Investment memo; gate checklist; dissent summary; decision
record.
Permissions and prohibitions No authority to approve, deploy, or modify evidence.
Activation triggers Candidate reaches committee gate; conditional review; model
expiry.
Key dependencies All validation agents; CIO; Risk Officer.
Success measures Completeness, traceability, zero missing gate artifacts.
### 3. Trading Operations Coordinator Agent
Division: Executive Coordination
Coordinates approved candidates through shadow, demo, micro-live, production, and retirement.
Core responsibilities Verify prerequisites; schedule releases; coordinate
deployment; track lifecycle; manage incident handoffs.
Required outputs Release plan; readiness checklist; lifecycle status; incident
coordination record.
Permissions and prohibitions Cannot change strategy logic, capital limits, or bypass
approvals.
Activation triggers Promotion decision; scheduled release; production incident.
Key dependencies Deployment; Risk; Reconciliation; Observability.
Success measures Release reliability, rollback readiness, incident resolution
quality.
### 4. Senior Quantitative Research Specialist Agent
Division: Research Intelligence
Acts as the firm’s principal quantitative research strategist and polymath reasoning system.
Core responsibilities Synthesize statistics, mathematics, physics, CS, econometrics,
stochastic processes, time series, ML, portfolio construction,
market microstructure, execution, and prior Invariance
evidence; propose falsifiable hypotheses; identify methods,
assumptions, sample requirements, failure modes, and
nonredundant directions; review independent research
quality.
Required outputs Cited research brief; formal hypothesis object; method
recommendation; prior-art map; assumptions register;
research critique.
Permissions and prohibitions Read-only access to approved knowledge and experiment
records; cannot run arbitrary code, see sealed holdouts,
approve promotion, deploy, or trade.
Activation triggers Research objective; unresolved anomaly; failed replication;
portfolio gap; literature update.
Key dependencies Research Intelligence Service; Hypothesis Architect;
Experiment Designer; Trial Registry.
Success measures Novel but defensible hypotheses, low redundancy, accurate
source use, high falsification yield, cumulative learning.
### 5. Market Literature Research Agent
Division: Research Intelligence
Retrieves and summarizes relevant academic and practitioner evidence.
Core responsibilities Search sources; extract methods; compare claims; identify
applicability and limitations; preserve citations.
Required outputs Literature dossier; evidence table; source passages; replication
notes.
Permissions and prohibitions No unsupported claims; cannot convert papers directly into
approved strategies.
Activation triggers Research question; requested method review; new source
ingestion.
Key dependencies Research Intelligence Service; Senior Specialist.
Success measures Citation accuracy, relevance, diversity, and reproducibility.
### 6. Crypto Market Structure Agent
Division: Research Intelligence
Generates domain-specific hypotheses from crypto mechanics.
Core responsibilities Study funding, basis, liquidations, open interest, exchange
fragmentation, stablecoin flows, leverage, token events, and
venue behavior.
Required outputs Market-structure memo; candidate mechanisms; data
requirements; event taxonomy.
Permissions and prohibitions No execution or exchange-account permissions.
Activation triggers New market event; research program; observed anomaly.
Key dependencies Market API; Alternative Data Scout; Event Researcher.
Success measures Unique crypto-specific hypotheses that survive basic
plausibility review.
### 7. Cross-Asset Research Agent
Division: Research Intelligence
Tests whether effects are universal, asset-class-specific, or hidden beta.
Core responsibilities Compare crypto, equity index futures, FX, rates, commodities,
and benchmarks; propose replication markets.
Required outputs Cross-market comparison; replication plan; hidden-exposure
assessment.
Permissions and prohibitions No strategy promotion authority.
Activation triggers Candidate effect; benchmark failure; portfolio concentration.
Key dependencies Market API; Benchmark Agent; Portfolio Agent.
Success measures Replication quality and reduction of market-specific false
conclusions.
### 8. Alternative Data Scout Agent
Division: Research Intelligence
Evaluates datasets before acquisition or use.
Core responsibilities Assess coverage, latency, licensing, quality, history,
survivorship, point-in-time properties, cost, and expected
research value.
Required outputs Data due-diligence memo; acquisition priority; schema
proposal.
Permissions and prohibitions Cannot purchase data or ingest unapproved sources.
Activation triggers New research need; vendor proposal; missing feature.
Key dependencies Data Engineer; Compliance; Research Director.
Success measures Useful data acquired per cost and avoided low-quality sources.
### 9. Hypothesis Architect Agent
Division: Quantitative Research
Converts observations into complete pre-registered hypothesis objects.
Core responsibilities Define mechanism, target, horizon, universe, expected effect,
null, failure conditions, cost sensitivity, and related trials.
Required outputs Machine-readable hypothesis specification.
Permissions and prohibitions Cannot modify hypothesis after seeing results without creating
a new version.
Activation triggers Approved research brief or human observation.
Key dependencies Senior Specialist; Trial Registry.
Success measures Completeness, falsifiability, and low post-hoc modification rate.
### 10. Experiment Specification Agent
Division: Quantitative Research
Transforms hypotheses into executable, machine-readable designs.
Core responsibilities Define features, labels, datasets, splits, purging, embargo,
controls, costs, stress, trial budget, and success criteria.
Required outputs Experiment manifest and validation plan.
Permissions and prohibitions Cannot view results before specification is locked; cannot
choose favorable tests post hoc.
Activation triggers Registered hypothesis approved for testing.
Key dependencies Feature Registry; Data API; Statistical Reviewer.
Success measures Executable specifications with no unresolved ambiguity or
leakage.
### 11. Signal Researcher Agent
Division: Quantitative Research
Determines whether a variable contains predictive information before trade rules are added.
Core responsibilities Forward-return surfaces; deciles; IC; monotonicity; horizons;
regime and asset breadth; gross/net feasibility.
Required outputs Signal evidence report; candidate signal object.
Permissions and prohibitions No full strategy optimization during signal stage.
Activation triggers Approved experiment manifest.
Key dependencies Executor; Statistical Service.
Success measures Stable, interpretable predictive relationships and high early
rejection rate.
### 12. Strategy Construction Agent
Division: Quantitative Research
Builds tradeable wrappers around validated signals.
Core responsibilities Entry, exit, holding, stops, execution type, throttling, risk unit,
and operational constraints.
Required outputs Versioned strategy specification.
Permissions and prohibitions Cannot alter underlying signal evidence or validation splits.
Activation triggers Signal passes discovery gate.
Key dependencies Execution Cost Agent; MFE/MAE models; Portfolio Agent.
Success measures Net monetization of signal without fragile parameterization.
### 13. Cross-Sectional Research Agent
Division: Quantitative Research
Researches rankings, residual returns, spreads, and relative-value portfolios.
Core responsibilities Rank assets; neutralize beta; test cross-sectional
persistence/reversal; control sectors and liquidity.
Required outputs Factor study; cross-sectional signal; neutralization
specification.
Permissions and prohibitions No direct order placement.
Activation triggers Cross-sectional research program.
Key dependencies Market API; Portfolio Agent.
Success measures Breadth, neutrality, replication, and distinct portfolio
contribution.
### 14. Time-Series Research Agent
Division: Quantitative Research
Researches temporal effects within instruments.
Core responsibilities Trend, carry, breakout, reversal, volatility conditioning,
persistence, and decay across horizons.
Required outputs Time-series signal report and candidate definitions.
Permissions and prohibitions No parameter winner selection without plateau analysis.
Activation triggers Time-series program.
Key dependencies Signal Researcher; Benchmark Agent.
Success measures Temporal stability and cost-adjusted significance.
### 15. Event-Driven Research Agent
Division: Quantitative Research
Researches discrete market and microstructure events.
Core responsibilities Liquidations, funding resets, announcements, volume shocks,
volatility shocks, gaps, and exchange events.
Required outputs Event taxonomy; event-study report; candidate event signals.
Permissions and prohibitions Cannot use future event knowledge or unverified timestamps.
Activation triggers Registered event research program.
Key dependencies Market Structure Agent; Data Quality.
Success measures Point-in-time-correct event effects with realistic tradability.
### 16. Machine Learning Research Agent
Division: Quantitative Research
Develops ML models for conditional decisions and forecasts.
Core responsibilities Baselines; feature selection; calibration; purged validation;
meta-labelling; expected return, risk, cost, and fill models.
Required outputs Model card; training manifest; validation report; inference
contract.
Permissions and prohibitions Cannot train on sealed holdouts, optimize classification
accuracy alone, or deploy itself.
Activation triggers Validated target and approved feature set.
Key dependencies Feature Agent; Statistical Reviewer; Model Risk.
Success measures Net incremental value, calibration, stability, and safe failure.
### 17. Regime Modelling Agent
Division: Quantitative Research
Creates and validates market-state representations.
Core responsibilities GMM, HMM, change points, clustering, transition analysis, and
downstream decision tests.
Required outputs Regime model card; state definitions; stability report.
Permissions and prohibitions Clusters are not accepted without downstream benefit.
Activation triggers Regime research program or model instability.
Key dependencies ML Agent; Portfolio; Risk Forecasting.
Success measures Improved decisions, stable states, and limited regime
concentration.
### 18. Feature Engineering Agent
Division: Quantitative Research
Creates causal, reusable, versioned features.
Core responsibilities Define formulas, availability timestamps, lags, normalization,
missing policy, transformations, redundancy, and lineage.
Required outputs Feature definition; tests; version; documentation.
Permissions and prohibitions Cannot silently change feature semantics or backfill
unavailable data.
Activation triggers New experiment or model feature request.
Key dependencies Market API; Leakage Auditor.
Success measures Timestamp correctness, reuse, low redundancy, and
batch/stream parity.
### 19. Autonomous Factor Explorer Agent
Division: Autonomous Discovery
Searches the constrained DSL for atomic predictive statements.
Core responsibilities Compose factors; propose mechanisms; query prior failures;
generate registered candidates within budgets.
Required outputs Candidate hypothesis and DSL expression.
Permissions and prohibitions No arbitrary Python, hidden data, strategy deployment, or
unregistered trials.
Activation triggers Bounded autonomous discovery session.
Key dependencies Research Governor; DSL Compiler; Trial Registry.
Success measures Useful novelty per trial, interpretability, and low rule
violations.
### 20. Symbolic Search Scheduler Agent
Division: Autonomous Discovery
Allocates candidate search using successive halving and value-of-information logic.
Core responsibilities Schedule cheap screens; promote fractions; enforce family
budgets; prevent early noise monopolization.
Required outputs Search plan; budget ledger; candidate funnel report.
Permissions and prohibitions Cannot change validation criteria or hide rejected candidates.
Activation triggers Discovery program approval.
Key dependencies Explorer; Compute Scheduler; Trial Registry.
Success measures Compute efficiency and calibrated survivor rates.
### 21. Market Adversary Agent
Division: Autonomous Discovery
Generates plausible hostile execution and market conditions.
Core responsibilities Perturb spreads, fees, latency, volatility, liquidity, correlation,
funding, gaps, and fill probabilities.
Required outputs Adversarial scenario set and fragility report.
Permissions and prohibitions Cannot modify canonical results or choose impossible
scenarios without labeling them.
Activation triggers Candidate enters robustness stage.
Key dependencies Stress Agent; Risk Forecasting.
Success measures Fragilities found before deployment and plausible scenario
coverage.
### 22. Synthetic Market League Agent
Division: Autonomous Discovery
Runs candidate policies against archived and synthetic participant mixtures.
Core responsibilities Maintain archived policies; simulate market makers, noise,
trend, reversion, liquidators, arbitrageurs, informed agents.
Required outputs League results; robustness diagnostics; exploitability report.
Permissions and prohibitions Results cannot count as real-market validation.
Activation triggers Approved synthetic research program.
Key dependencies Agent-based simulator; Research Governor.
Success measures Behavioral robustness and reduced single-opponent
exploitation.
### 23. Laboratory Red Team Agent
Division: Autonomous Discovery
Attempts to exploit the research environment itself.
Core responsibilities Probe holdouts, filenames, caches, cost settings, NaNs, bar
boundaries, permissions, output overwrites, and query side
channels.
Required outputs Security finding; exploit reproduction; remediation test.
Permissions and prohibitions No production secrets or destructive actions beyond isolated
sandbox.
Activation triggers Scheduled red-team cycle or architecture change.
Key dependencies Security Agent; Research Governor.
Success measures Cheating paths detected and closed.
### 24. Live Anomaly Scout Agent
Division: Autonomous Discovery
Observes live data for unmodeled behavior without trading new discoveries.
Core responsibilities Detect drift, unusual relationships, unexplained cost changes,
and candidate anomalies; create research observations.
Required outputs Anomaly record; proposed research question; supporting live
evidence.
Permissions and prohibitions Cannot rewrite or trade strategies; observations must re-enter
registration.
Activation triggers Fast-clock live observation.
Key dependencies Shadow Service; Research Registry.
Success measures Useful anomalies, low false-alarm burden, zero unauthorized
adaptation.
### 25. Research Governor Agent
Division: Autonomous Discovery
Controls objectives, permissions, budgets, holdouts, and promotion gates.
Core responsibilities Issue bounded mandates; enforce trial limits; validate allowed
tools; stop violations; route approvals.
Required outputs Governance record; budget decision; gate result.
Permissions and prohibitions Cannot invent alpha, modify evidence, or approve capital
alone.
Activation triggers Every autonomous session and promotion request.
Key dependencies Control Plane; Human approvers; Security.
Success measures No gate bypasses, budget compliance, and complete audit
trails.
### 26. Research Execution Agent
Division: Autonomous Discovery
Executes approved manifests through Bulletproof BT and auxiliary tools.
Core responsibilities Compile DSL; launch jobs; preserve configs; collect outputs;
report failures; never alter hypothesis post-result.
Required outputs Run artifacts; logs; checksums; status.
Permissions and prohibitions Cannot modify data, engine, fee models, splits, or experiment
records.
Activation triggers Approved experiment manifest.
Key dependencies Backtest Orchestrator; Artifact Store.
Success measures Reproducibility, job integrity, and low execution error.
### 27. Statistical Reviewer Agent
Division: Independent Validation
Independently reproduces results in a clean workspace and evaluates evidence with trial-aware statistical
methods.
Core responsibilities Clean-workspace reproduction; code/data/config verification;
effect size; confidence; bootstrap; dependence; effective
sample; DSR; PBO; FDR; stability; economic significance.
Required outputs Statistical validation report and confidence grade.
Permissions and prohibitions Cannot redesign hypothesis after results or approve live
capital.
Activation triggers Completed experiment set.
Key dependencies Trial Registry; Statistical Service.
Success measures Calibration of judgments and reduction of false positives.
### 28. Leakage and Bias Auditor Agent
Division: Independent Validation
Detects lookahead, timestamp, universe, survivorship, overlap, and data leakage.
Core responsibilities Audit availability; labels; splits; delistings; duplicates; feature
lineage; execution alignment.
Required outputs Leakage report; severity; remediation requirement.
Permissions and prohibitions Can block promotion; cannot repair silently.
Activation triggers Every candidate validation and data change.
Key dependencies Data Quality; Feature Registry; Market API.
Success measures Leakage caught before promotion and zero unresolved critical
findings.
### 29. Adversarial Research Auditor Agent
Division: Independent Validation
Attempts to disprove the economic and empirical claim.
Core responsibilities Alternative explanations; hidden beta; one-period dependence;
benchmark attacks; mechanism challenges; counterfactual
tests.
Required outputs Adversarial review; competing hypotheses; kill
recommendation.
Permissions and prohibitions Cannot modify candidate or selectively omit favorable
evidence.
Activation triggers Candidate passes initial statistics.
Key dependencies Benchmark Agent; Cross-Asset Agent.
Success measures Weak candidates killed early and useful competing
explanations.
### 30. Robustness and Stress Agent
Division: Independent Validation
Tests sensitivity to costs, data, delay, outages, universes, parameters, and structural breaks.
Core responsibilities Fee/slippage/delay stress; missing data; partial fills; alternate
bars; asset/year removal; neighboring parameters.
Required outputs Robustness matrix and survival grade.
Permissions and prohibitions Cannot choose only favorable stresses.
Activation triggers Candidate enters robustness state.
Key dependencies Market Adversary; Execution Models.
Success measures Coverage and correlation with future live degradation.
### 31. Benchmark and Replication Agent
Division: Independent Validation
Compares complexity with simple baselines and external replications.
Core responsibilities Buy/hold; simple trend; simple reversion; matched random;
volatility-scaled; turnover-matched; cross-market replication.
Required outputs Benchmark report; incremental-value decision.
Permissions and prohibitions Cannot approve complexity without demonstrated value.
Activation triggers Any candidate or ML model.
Key dependencies Cross-Asset Research; Portfolio.
Success measures Complexity justified and hidden exposure identified.
### 32. Forecast Normalization Agent
Division: Portfolio and Risk
Converts heterogeneous signals into comparable, calibrated forecasts.
Core responsibilities Scale, winsorize, calibrate, uncertainty-discount, and monitor
forecast distributions.
Required outputs Standardized forecast stream and calibration report.
Permissions and prohibitions Cannot create new alpha or exceed approved ranges.
Activation triggers Signal admission or periodic recalibration.
Key dependencies Signal Library; Model Risk.
Success measures Stable comparable forecasts and prospective calibration.
### 33. Portfolio Construction Agent
Division: Portfolio and Risk
Combines forecasts under risk, cost, liquidity, and concentration constraints.
Core responsibilities Optimize allocation; cap exposure; penalize turnover; model
covariance; handle constraints and uncertainty.
Required outputs Target portfolio; constraint report; expected risk and cost.
Permissions and prohibitions Cannot override hard risk limits or use unapproved signals.
Activation triggers Portfolio rebalance or candidate admission.
Key dependencies Risk Forecasting; Allocation; Prop Overlay.
Success measures Net portfolio efficiency, diversification, and constraint
compliance.
### 34. Strategy Allocation Agent
Division: Portfolio and Risk
Allocates risk across strategy sleeves based on marginal value.
Core responsibilities Evaluate correlation, drawdown, capacity, confidence, decay,
and redundancy; recommend scale/deallocation.
Required outputs Sleeve allocation recommendation.
Permissions and prohibitions Cannot allocate solely on recent P&L or increase firm limits.
Activation triggers Periodic allocation review or candidate admission.
Key dependencies Portfolio Construction; Performance Analyst.
Success measures Marginal contribution and controlled concentration.
### 35. Risk Forecasting Agent
Division: Portfolio and Risk
Forecasts volatility, covariance, tail risk, concentration, and liquidation exposure.
Core responsibilities Scenario analysis; stress correlations; regime risks; liquidity-
adjusted risk; uncertainty ranges.
Required outputs Risk forecast and scenario pack.
Permissions and prohibitions No trading or limit increases.
Activation triggers Pre-allocation, daily risk cycle, regime shift.
Key dependencies Market Data; Regime Agent.
Success measures Risk forecast calibration and early warning value.
### 36. Prop-Firm Constraint Agent
Division: Portfolio and Risk
Implements account-provider rules as a separate portfolio overlay.
Core responsibilities Daily loss, max/trailing drawdown, leverage, overnight, event,
consistency, payout, reset, and breach simulations.
Required outputs Pass probability; breach probability; time-to-target; survival
score; risk multiplier.
Permissions and prohibitions Cannot redefine alpha or use stale provider rules.
Activation triggers Provider selection; account change; portfolio review.
Key dependencies Risk Engine; Operations; current rule configuration.
Success measures Accurate rule enforcement and funded-account survival.
### 37. Pre-Trade Risk Agent
Division: Risk Control
Produces deterministic approve, reduce, reject, or halt decisions before orders.
Core responsibilities Check authorization, exposure, leverage, drawdown, liquidity,
stale data, account rules, and duplicate intent.
Required outputs Signed risk decision with reasons.
Permissions and prohibitions Cannot be overridden by execution; LLM commentary is
nonbinding.
Activation triggers Every proposed order.
Key dependencies Deterministic Risk Engine; Prop Overlay.
Success measures Zero unauthorized orders and predictable latency.
### 38. Real-Time Risk Sentinel Agent
Division: Risk Control
Monitors live risk and invokes deterministic protection.
Core responsibilities Positions, P&L, drawdown, leverage, correlations, data health,
abnormal fills, exchange health, and strategy divergence.
Required outputs Alerts; cancel/reduce/halt instructions; incident record.
Permissions and prohibitions May reduce or halt; may not increase limits or initiate
discretionary trades.
Activation triggers Continuous live operation.
Key dependencies Risk Engine; OMS; Observability.
Success measures Loss containment, fast detection, no false increases.
### 39. Model Risk Agent
Division: Risk Control
Monitors assumptions, drift, calibration, support, and decay.
Core responsibilities Feature drift; forecast drift; calibration; performance decay;
review dates; model inventory.
Required outputs Model risk status; pause/review recommendation.
Permissions and prohibitions Cannot retrain or deploy models independently.
Activation triggers Scheduled review or threshold breach.
Key dependencies ML Models; Shadow; Performance.
Success measures Early decay detection and controlled model lifecycle.
### 40. Operational Risk Agent
Division: Risk Control
Monitors infrastructure and process failure risks.
Core responsibilities Connectivity; credentials; duplicate orders; backups;
reconciliation; permissions; incident controls.
Required outputs Operational risk dashboard; incidents; remediation tracking.
Permissions and prohibitions May halt affected workflows; cannot alter trading logic.
Activation triggers Continuous operation and release events.
Key dependencies Security; Observability; Reconciliation.
Success measures Reduced operational incidents and rapid containment.
### 41. Execution Strategy Agent
Division: Trading and Execution
Selects approved execution tactics and venues for target orders.
Core responsibilities Market/passive choice; urgency; slicing; venue comparison;
spread/depth; fees; funding; fill probability; adverse selection;
inventory and counterparty awareness.
Required outputs Execution plan and expected cost.
Permissions and prohibitions Cannot alter target position or bypass risk.
Activation triggers Approved target order.
Key dependencies Cost Model; Market Data; OMS.
Success measures Implementation shortfall versus benchmark.
### 42. Order Management Agent
Division: Trading and Execution
Runs deterministic order state management.
Core responsibilities Create, acknowledge, cancel, replace, retry, handle partial fills,
prevent duplicates, and persist states.
Required outputs Order and event records.
Permissions and prohibitions No free-form discretionary behavior; cannot override risk or
change strategy.
Activation triggers Approved order.
Key dependencies Exchange Adapter; Risk Decision.
Success measures State integrity, low error, no duplicate orders.
### 43. Execution Quality Analyst Agent
Division: Trading and Execution
Measures predicted versus realized execution.
Core responsibilities Implementation shortfall; fill ratio; latency; adverse selection;
fees; funding; cost-model residuals.
Required outputs Execution-quality report and cost-model feedback.
Permissions and prohibitions Cannot rewrite historical fills or hide bad execution.
Activation triggers Post-trade and daily review.
Key dependencies Orders; Fills; Cost Models.
Success measures Cost prediction accuracy and execution improvement.
### 44. Position Reconciliation Agent
Division: Trading and Execution
Independently reconciles internal and external records.
Core responsibilities Positions, balances, open orders, fills, fees, funding, and cash
movements.
Required outputs Reconciliation status and discrepancy incidents.
Permissions and prohibitions Independent from OMS; may block new trading on critical
mismatch.
Activation triggers Scheduled intervals and post-incident.
Key dependencies Exchange APIs; Ledger; OMS.
Success measures Zero unexplained material discrepancies.
### 45. Shadow Market Agent
Division: Trading and Execution
Runs prospective live observation without capital.
Core responsibilities Compute registered features; predictions; hypothetical orders;
expected and observable fills; latency; forward returns;
divergence.
Required outputs Shadow dataset and prospective validation report.
Permissions and prohibitions Cannot place live orders or modify research definitions.
Activation triggers Candidate enters shadow state.
Key dependencies Live Data; Signal Service; Cost Models.
Success measures Prospective calibration, implementation realism, and data
parity.
### 46. Market Data Ingestion Agent
Division: Data and Platform
Ingests raw and reference market data reliably.
Core responsibilities Trades, bars, books, funding, open interest, liquidations,
instrument metadata, and exchange status.
Required outputs Versioned raw datasets; ingestion logs; checksums.
Permissions and prohibitions Cannot silently transform or impute raw data.
Activation triggers Continuous feeds or backfill job.
Key dependencies Vendor/Exchange APIs; Storage.
Success measures Completeness, timeliness, and exact replayability.
### 47. Data Quality and Curation Agent
Division: Data and Platform
Detects defects and produces approved curated snapshots.
Core responsibilities Missing/duplicate/stale timestamps; symbol maps; universe
history; delistings; anomalies; quarantine; manifests.
Required outputs Quality report; curated snapshot; manifest; quarantine record.
Permissions and prohibitions May quarantine; may not silently repair or overwrite raw data.
Activation triggers New data arrival, snapshot creation, or anomaly.
Key dependencies Ingestion; Research Registry.
Success measures Defect detection, point-in-time correctness, and reproducibility.
### 48. Backtest Orchestration and Compute Agent
Division: Data and Platform
Schedules Bulletproof BT and research jobs under budgets.
Core responsibilities Queue, CPU/RAM allocation, deduplication, retries, manifests,
hashes, artifact collection, and cost accounting.
Required outputs Job status; run artifacts; compute ledger.
Permissions and prohibitions Cannot change parameters after launch or prioritize
unapproved work.
Activation triggers Approved experiment or scheduled job.
Key dependencies Control Plane; Workers; Artifact Store.
Success measures Throughput, reproducibility, resource efficiency, and fairness.
### 49. Deployment and Observability Agent
Division: Data and Platform
Builds, deploys, monitors, and rolls back approved packages.
Core responsibilities Containers; migrations; health checks; release hashes; logs;
metrics; traces; alerts; rollback.
Required outputs Deployment record; health report; rollback result.
Permissions and prohibitions Requires signed approval; cannot change strategy or risk
config.
Activation triggers Approved release or incident.
Key dependencies CI/CD; VM2; Observability Stack.
Success measures Release reliability, uptime, and rollback success.
### 50. Security and Access Agent
Division: Data and Platform
Enforces least privilege, secrets safety, and agent boundaries.
Core responsibilities Policies; secret rotation; access audit; unauthorized-action
detection; host boundaries; credential scopes.
Required outputs Access decision; audit report; security incident.
Permissions and prohibitions Cannot expose secrets to research agents or broaden
permissions without approval.
Activation triggers Agent creation, permission change, scheduled audit, incident.
Key dependencies Control Plane; Vault; Human Security Owner.
Success measures No critical secret exposure or unauthorized privilege
expansion.
### 51. Research Registry and Knowledge Graph Agent
Division: Governance and Memory
Maintains canonical institutional memory and relationships.
Core responsibilities Record hypotheses, trials, features, datasets, results, reviews,
decisions, related ideas, failures, and lineage; support
similarity and contradiction search.
Required outputs Immutable records; relationship graph; retrieval index; trial
counts.
Permissions and prohibitions Cannot delete negative results or alter historical records
without controlled correction event.
Activation triggers Every research action and conclusion.
Key dependencies PostgreSQL/pgvector; Artifact Store.
Success measures Completeness, retrieval usefulness, and zero orphaned
promoted models.
### 52. Post-Trade Attribution and Firm Performance Agent
Division: Governance and Memory
Explains firm outcomes and feeds production learning back into research.
Core responsibilities Attribute P&L by strategy, asset, direction, signal, regime,
execution, fees, funding, beta, and risk; compare live to
expected; prepare daily/weekly/monthly reviews.
Required outputs Performance report; live-degradation report; research
feedback; retirement triggers.
Permissions and prohibitions Cannot alter books, approve capital, or hide negative
attribution.
Activation triggers Daily close, weekly review, drawdown, and model review.
Key dependencies Ledger; Portfolio; Execution; Registry.
Success measures Accurate attribution, actionable degradation diagnosis, and
learning-loop closure.
## 10. Permissions, Governance, and Decision Rights
### 10.1 Permission classes
Class Rights
A - Read-only research Read approved datasets, knowledge, and records; propose
artifacts; no canonical writes except proposals.
B - Research execution Submit approved jobs in isolated workspaces; write immutable
artifacts; no production or holdout access.
C - Independent validation Rerun, audit, reject, and flag; no editing of original research or
live capital approval.
D - Production operations Deploy signed packages and operate approved systems; no
strategy or limit changes.
E - Risk control Reduce, cancel, halt, and quarantine; never increase limits or
initiate discretionary positions.
### 10.2 Human decision rights
- Founder/CIO: research priorities, approved markets, investment philosophy, live promotion, capital
allocation, and scaling.
- Head of Quantitative Research: research standards, experiment approval, and research-program
governance.
- Independent Risk Owner: firm-level limits, pause decisions, and authority to stop trading.
- Technology Owner: production architecture, release standards, security, and reliability.
- Compliance/Operations Owner: accounts, records, external rules, legal and operational obligations.
### 10.3 Deterministic versus agentic boundary
- Agentic: research retrieval, hypothesis generation, experiment design, code drafting, interpretation,
critique, anomaly investigation, documentation, and coordination.
- Deterministic: position arithmetic, order generation, duplicate prevention, maximum loss, leverage, prop
rules, kill switches, balance checks, reconciliation, approval verification, and secret enforcement.
### 10.4 Required separation of duties
- No proposer approves its own experiment or promotion.
- No execution agent changes approved logic or risk limits.
- No deployment agent approves its own release.
- No risk agent increases exposure.
- No research agent sees detailed sealed-holdout diagnostics.
- No production worker simultaneously has unrestricted source, database, secrets, exchange, and risk-config
access.
## 11. Data, Metadata, and Experiment Contracts
### 11.1 Required source metadata
source_id, title, author, year, document_type, subject, chapter, section, page,
keywords, mathematical_topics, financial_topics, markets, time_horizon, methodology,
assumptions, evidence_type, citation
### 11.2 Required experiment metadata
experiment_id, hypothesis_id, research_family, repository_commit, dataset_version,
instrument_universe, timeframe, date_range, features, target, model_or_rule, parameters,
fees, slippage, delay, number_of_trials, validation_method, result, robustness_status,
rejection_reason, created_at, agent_identity, approval_id
### 11.3 Required label contract
- Label definition and exact decision meaning.
- Label start and label_end_time.
- Prediction timestamp and feature availability timestamp.
- Overlap, purging, embargo, and sample-weighting policy.
- Costs, barriers, horizon, censoring, and missing-data policy.
- Universe and eligibility rules at each point in time.
### 11.4 Required immutable lineage
HYPOTHESIS -> DATA SNAPSHOT -> FEATURE VERSION -> EXPERIMENT MANIFEST
-> CODE COMMIT -> ENGINE CONFIG -> RUN OUTPUT -> VALIDATION REPORTS
-> APPROVAL -> CONTAINER HASH -> LIVE DECISIONS -> ORDERS -> FILLS -> ATTRIBUTION
### 11.5 Primary database domains
research_sources, research_documents, research_chunks, research_citations,
research_hypotheses, research_experiments, research_trials, research_results,
research_reviews, research_decisions, research_relationships, feature_definitions,
data_snapshots, validation_splits, candidate_signals, promotion_decisions,
shadow_predictions, live_degradation, agent_actions, incidents, orders, fills, positions
## 12. Promotion State Machine and Stage Gates
PROPOSED -> SCREENED -> REPLICATED -> ROBUST -> SHADOW -> MICRO_LIVE
-> PORTFOLIO_ELIGIBLE -> PRODUCTION -> DEGRADED -> RETIRED
State Minimum gate
PROPOSED Registered hypothesis, rationale, target, null, failure
conditions, trial family, and approved research budget.
SCREENED Minimum effect evidence, no obvious leakage, viable data,
plausible cost envelope, and no dependence on a single
configuration.
REPLICATED Independent reproduction and evidence across periods,
instruments, definitions, or markets as appropriate.
ROBUST Trial-aware statistics, adversarial review, stress survival,
baseline comparison, and documented limitations.
SHADOW Production-parity features and decisions; prospective data,
cost, fill, latency, and calibration evidence.
MICRO_LIVE Minimal-capital implementation validation; correct order
lifecycle, risk, reconciliation, and acceptable cost divergence.
PORTFOLIO_ELIGIBLE Positive marginal contribution, capacity, manageable
correlation, risk fit, and approved allocation range.
PRODUCTION Human CIO and Risk approval, signed deployment artifact,
monitoring, rollback, and retirement criteria.
DEGRADED Threshold breach in calibration, cost, performance, drift, risk,
or operations; allocation reduced or paused.
RETIRED Evidence no longer supports use, implementation is
uneconomic, or portfolio value is superseded; full history
retained.
### 12.1 Sealed holdout behavior
The Explorer receives only a pass/fail gate and coarse failure category from sealed historical holdouts. Detailed
years, instruments, and parameter diagnostics remain unavailable to prevent repeated adaptation to the
holdout.
{
"passed": false,
"failure_category": "temporal_instability"
}
## 13. Deployment Topology
### 13.1 VM1 - research development
- Document ingestion, retrieval, vector indexing, experiment schemas, feature/alpha DSL, Bulletproof BT
adapters, research tests, Senior Quantitative Research Specialist, Hypothesis Architect, Experiment
Designer, ML Research, Statistical Reviewer, and Adversarial Auditor.
- Isolated agent workspaces and non-production credentials.
- Primary development and experimentation environment.
### 13.2 VM2 - durable control and production
- Research Intelligence API, PostgreSQL/pgvector, trial registry, task orchestration, artifact registry,
production knowledge service, scheduled jobs, shadow service, portfolio services, execution, deterministic
risk, reconciliation, observability, and production containers.
- Production secrets are scoped by service and unavailable to research profiles.
- Immutable records and durable backups reside here.
### 13.3 Mac - founder command and review
- Research chat, dashboard, literature upload, hypothesis review, approval workflow, decision journal,
performance review, and optional Telegram control interface.
- No requirement for persistent production hosting.
- Used to direct, inspect, approve, and review the firm rather than execute unattended trading.
### 13.4 Three clocks of live operation
- Fast clock - every bar/tick: compute registered features, score approved signals, monitor execution and
drift; no research changes.
- Medium clock - daily/weekly: score prospective predictions, update calibration, evaluate costs, and detect
distribution shifts.
- Slow clock - weekly/monthly: generate hypotheses, retrain approved models, run validation, and promote
only through governance.
## 14. Phased Delivery Roadmap
Phase Primary delivery Exit condition
RI-1 Research Knowledge Foundation Ingestion, parsing, metadata,
PostgreSQL/pgvector, hybrid search,
source retrieval, citation preservation,
retrieval evaluation.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
RI-2 Senior Quantitative Research
Specialist
Cited research synthesis, prior-
experiment inspection, structured
hypothesis generation, methods,
assumptions, and failure conditions.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
RI-3 Trial Registry and Experiment
Contracts
Global trial IDs, immutable manifests,
data/code lineage, family counts,
negative results, and selection-aware
records.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
RI-4 Closed Five-Agent Research Loop Senior Specialist, Experiment
Specification, Execution, Statistical
Reviewer, and Adversarial Auditor with
human approval.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
ADL-1 Feature/Alpha DSL and Market
API
Constrained symbolic language, causal
compiler, point-in-time API, query
logging, and sealed holdouts.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
ADL-2 Autonomous Factor Miner Explorer, search scheduler, successive
halving, bounded candidate generation,
and interpretability.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
ADL-3 Adversarial Research League Market adversary, red team, falsifier,
governor, and trial-aware discovery
score.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
ML-1 Reality-Aligned Labels and Barrier labels, label_end_time, Acceptance tests passed; artifacts
Phase Primary delivery Exit condition
Baselines logistic/linear baselines, calibrated meta-
labelling, cost and fill models.
registered; human owner signs phase
completion.
PV-1 Signal Library and Portfolio
Validation
Forecast normalization, portfolio
contribution, covariance, capacity,
turnover, and prop overlay.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
SH-1 Shadow Market Service Prospective features, predictions,
hypothetical orders, observable fills,
latency, and live degradation.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
LIVE-1 Micro-Live and Deterministic
Operations
OMS, pre-trade risk, real-time risk,
reconciliation, incident response, and
minimal-capital validation.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
SCALE-1 Controlled Production Allocation governance, scaling criteria,
continuous model risk, attribution,
retirement, and feedback into research.
Acceptance tests passed; artifacts
registered; human owner signs phase
completion.
### 14.1 First working demonstration
23. Upload a statistics text, time-series text, selected papers, and Invariance experiment reports.
24. Ask one quantitative research question.
25. Retrieve exact relevant passages and prior experiment records.
26. Generate one cited, structured hypothesis.
27. Check the proposal against similar and failed Invariance experiments.
28. Generate a locked experiment specification with costs, validation, and failure conditions.
29. Require human approval before Bulletproof BT execution.
30. Return the result to independent statistical and adversarial review.
31. Register the complete trial regardless of outcome.
## 15. Metrics and Acceptance Criteria
### 15.1 Research system metrics
- Percentage of hypotheses falsified cheaply before full backtesting.
- Time from research question to registered experiment.
- Replication rate and trial-adjusted survivor rate.
- Number of genuinely independent signal families.
- Redundant or repeated research avoided through institutional memory.
- Value of information per compute unit.
- Ratio of negative to positive results retained and retrievable.
### 15.2 Validation metrics
- Critical leakage issues found before promotion.
- Reproduction success rate.
- Calibration of statistical confidence grades versus prospective performance.
- Correlation between stress results and live degradation.
- Percentage of complex models that beat transparent baselines net of costs.
### 15.3 Portfolio and production metrics
- Marginal portfolio contribution, drawdown, diversification, turnover, capacity, and cost survival.
- Predicted versus realized volatility, correlation, cost, fill, and slippage.
- Shadow-to-live parity and live degradation decomposition.
- Operational error rate, duplicate-order rate, reconciliation breaks, uptime, and kill-switch latency.
- Prop-firm pass probability, breach probability, expected account lifetime, and expected payout before
breach.
### 15.4 Agent quality metrics
- Tasks completed without human correction.
- Output-schema compliance and evidence traceability.
- Unauthorized action attempts blocked.
- Duplicate work avoided.
- Useful findings per tool call and compute unit.
- Escalation quality and reviewer acceptance rate.
- Failure to disclose negative evidence or conflicts: target zero.
### 15.5 Product acceptance criteria
- Every promoted model has complete immutable lineage.
- No candidate can skip the state machine.
- Every autonomous session has an objective, trial budget, compute budget, allowed tools, and stop
condition.
- No research agent can access sealed holdout details or production secrets.
- All live orders require deterministic pre-trade approval.
- Positions, orders, fills, balances, and risk are independently reconciled.
- Every live strategy has warning, reduction, pause, rollback, and retirement criteria.
- Negative results remain searchable and influence future proposals.
- Live degradation is measured and classified before scaling.
## 16. Risks, Failure Modes, and Guardrails
Risk Required guardrail
Automated p-hacking Trial registry, family counts, sealed holdouts, FDR, DSR, PBO,
compute budgets, and almost no reward for in-sample
performance.
Leakage and timestamp artifacts Point-in-time API, availability metadata, label_end_time,
purging, embargo, delayed features, and independent audit.
Simulator exploitation Constrained DSL, immutable engine, red-team testing,
alternate bar construction, and production parity.
One-agent conflict of interest Separation among proposer, designer, executor, reviewer,
falsifier, governor, deployer, and risk owner.
Research memory loss Canonical registry, knowledge graph, artifact lineage, and
mandatory recording of failures.
Model complexity creep Transparent baselines, complexity penalty, incremental-value
gates, and model cards.
Live self-modification Three-clock architecture; live anomaly scouts can propose but
cannot trade new discoveries.
Prop-rule overfitting Separate overlay and provider-specific configuration; alpha
remains provider-agnostic.
Operational loss Deterministic risk, reconciliation, scoped secrets, observability,
rollback, backups, and incident playbooks.
False confidence from synthetic markets Synthetic results are robustness evidence only; historical,
Risk Required guardrail
shadow, and micro-live evidence remain mandatory.
Over-centralized language model Research intelligence belongs to shared services and databases
so models can be replaced without losing memory.
Human rubber-stamping Decision memos expose dissent, unresolved risks, evidence
grades, and explicit approval accountability.
## 17. Appendices
### Appendix A - Standard hypothesis object
hypothesis_id: HYP-2026-0017
title: Volatility-conditioned intraday continuation
research_family: momentum
status: proposed
research_question: Does directional continuation increase after volatility expansion
when order-flow imbalance and cross-sectional strength agree?
rationale:
mathematical: [conditional dependence, volatility clustering, state-dependent returns]
market: [delayed information incorporation, liquidity-taking continuation]
sources:
- {source_id: PAPER-0012, relevant_section: Section 4}
- {source_id: BOOK-0043, relevant_section: Chapter 9}
universe: {market: crypto_perpetuals, instruments: liquid_usdt_perpetuals, timeframe: 5m}
features: [realized_volatility, cross_sectional_return_rank, volume_imbalance, funding_rate,
spread_proxy]
target: {type: forward_return, horizon_bars: 12}
null_hypothesis: Conditional forward return is not different from zero after costs.
validation: [expanding_walk_forward, purged_cv, embargo, bootstrap, multiple_testing_adjustment,
fee_stress, slippage_stress, delay_stress, regime_stability]
failure_conditions: [cost_failure, one_instrument_only, narrow_parameter_peak, oos_failure,
infeasible_turnover]
priority: medium
estimated_compute: moderate
### Appendix B - Standard autonomous research mandate
Objective: Investigate whether volatility expansion modifies short-term continuation
across liquid crypto perpetuals.
Limits:
max_hypotheses: 20
max_model_specifications: 100
fixed_compute_budget: true
live_deployment: prohibited
promotion_without_approval: prohibited
Required outputs:
registered hypotheses, full trial ledger, screening results, validation results,
negative results, adversarial findings, and final research conclusion
### Appendix C - Pre-deployment checklist
- Complete hypothesis, experiment, data, feature, model, and code lineage.
- Independent reproduction completed.
- Leakage and bias audit resolved.
- Trial-aware statistics and adversarial validation complete.
- Portfolio contribution and capacity approved.
- Shadow evidence demonstrates production parity and acceptable prospective behavior.
- Micro-live plan, risk limits, kill switches, reconciliation, monitoring, and rollback tested.
- Human CIO, Risk, and Technology approvals recorded.
- Warning, reduction, pause, degradation, and retirement criteria configured.
### Appendix D - Foundational doctrine
What the firm can guarantee
The firm cannot guarantee profitable alpha. It can build a structural advantage in search, falsification, execution learning,
portfolio combination, and adaptation. That process advantage is the product.
What the firm is building
Not an agent that always finds an edge, but a closed autonomous research institution in which one agent proposes, another
formalizes, another executes, another attacks, another controls selection bias, another observes live behavior, another governs
promotion, every action is recorded, and no agent can alter the rules used to judge itself.
END OF PRODUCT REQUIREMENTS DOCUMENT
