
# Hermes Research Milestones M14-M24

This roadmap follows the trading-firm PRD's scientific ordering. A milestone may not
consume authority assigned to a later milestone. In particular, research evidence is
never trading authority.

## M14: Daily supervised research

Schedule one bounded question per day, enforce compute and trial budgets, suppress
duplicate questions, publish a daily digest and weekly program metrics, and run the
existing separated research loop without terminal timing races.

Exit: source, deployment, and a first duplicate-control pilot pass. Operational exit
requires multiple weeks of complete records without gate bypasses or terminal
babysitting.

## M14C: Operational Memory Steward

Implementation status: complete. Production migration `e1c4a7b92d60`, signed identity
bootstrap, first-note deferral pilot, Mac Mission Control retrieval, and VM2 Telegram
deployment were validated on 2026-08-01. See
[the M14C validation record](m14c-operational-memory-steward.md).

Add a non-executing note-taking agent that records durable observations from the
founder and other agents using an immutable structured contract: subject, finding,
evidence, affected systems, urgency, proposed owner, deferral reason, status, and
resolution evidence. Notes must be searchable in Mission Control and Telegram,
deduplicated by digest, linked to milestones or repositories, and convertible into
proposals only through the normal founder approval boundary. The Steward cannot edit
repositories, dispatch tasks, approve work, or silently close its own notes.

First note: [system-wide storage efficiency](notes/system-wide-storage-efficiency.md),
starting with the unexpectedly large Bulletproof research-memory database observed
during the M14B bridge validation.

Exit: one dedicated role-package identity can create, deduplicate, search, assign,
defer, and close notes through an audited API and Mission Control view; the first
storage-efficiency note has an approved audit task or an explicit deferral date.

## M15: Point-in-time data and feature contracts

Implementation status: source-complete; production migration and the two-dataset
digest-bound pilot remain operational exit gates. See
[the M15 design and rehearsal](m15-point-in-time-data-contracts.md).

Create provider-aware data manifests, as-of semantics, quality flags, corporate-action
handling, feature lineage, and deterministic dataset builds. No silent provider
fallbacks.

Exit: two independent real datasets rebuild bit-for-bit from registered manifests.

## M16: Trial-aware statistics and sealed holdouts

Add purging, embargo, dependence-aware uncertainty, bootstrap confidence intervals,
deflated/selection-adjusted statistics, family-wide trial accounting, and sealed
holdout access controlled by a separate role.

Exit: one candidate survives or fails a blinded holdout without exploratory access.

## M17: Bounded alpha discovery laboratory

Introduce a typed signal DSL and budgeted human-, literature-, and memory-led search.
Every generated variant is registered before evaluation; broad unconstrained mining
remains prohibited.

ALPHA-004 adds the continuous production feeder for this milestone: separately
chartered RI and senior-research agents, weekly digest-bound no-capital mandates,
DATA-002/003 admission, predictive/falsifiability rejection, DISC-009 replenishment,
BT-009 campaign creation, outcome feedback, and Mission Control throughput/stall
visibility. LLM-assisted equations remain source-bound and cannot self-certify.
RI-014D makes equation use just-in-time and cached: two parser families plus
deterministic token, AST and source checks can issue a machine receipt, while
stronger independence requires an AGT-006 receipt and disagreements fail closed
visibly. Migration `a0d6e8f92b51` and live report
`675ffd7409aedb864dd535272ff89b150ef9ce0a2e1afa65310d1ac7cf10ed4c`
demonstrated cache reuse, mismatch rejection and a source-bound
`machine_verified` receipt. ALPHA-004 operational exit separately requires three
active supervised services, one approved weekly mandate and a terminal real-data
campaign attempt.

Exit: a fixed discovery budget produces a complete searchable family including every
failure.

## M18: Signal promotion and research portfolio

Define evidence grades, plateau/stability requirements, dissent handling, correlation
and redundancy checks, and promotion states from rejected through shadow-eligible.

Exit: multiple signals are ranked as institutional research assets without receiving
capital authority.

## M19: Portfolio construction and deterministic risk

Implement covariance and regime-aware allocation, concentration and exposure limits,
drawdown controls, liquidity constraints, and prop-firm overlays in deterministic code.

Exit: approved signals form a reproducible constrained paper portfolio.

## M20: Costs, capacity, and execution simulation

Model spread, fees, slippage, impact, borrow/funding, latency, turnover, and capacity;
support optional independent LEAN replication for implementation-sensitive candidates.

Exit: the paper portfolio passes declared net-economics and capacity stresses.

## M21: Shadow trading and reconciliation

Run live-data, zero-capital shadow decisions with deterministic order simulation,
position/account reconciliation, alerts, and prospective performance attribution.

Exit: a sustained shadow period has complete decisions, reconciliations, and incident
records.

## M22: Micro-live governance and readiness

Add capital mandates, dual approval, kill switches, venue credential isolation,
pre-trade limits, incident response, and tiny-capital readiness reviews. No language
model can place or alter an order.

Exit: rehearsal and governance evidence support an explicit founder micro-live decision.

## M23: Deterministic production execution

Deploy a minimal deterministic execution service with order state machines,
idempotency, reconciliation, fail-safe shutdown, and independently monitored limits.

Exit: explicitly approved micro-live operation completes within every risk boundary.

## M24: Attribution and institutional learning

Attribute performance to signal, portfolio, cost, timing, regime, and implementation;
calibrate forecasts; detect decay; feed cited lessons and negative evidence back into
daily research priorities.

Exit: weekly and monthly reviews close the loop from prospective claim to realized
outcome and next registered question.
