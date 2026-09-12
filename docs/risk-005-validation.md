# RISK-005 validation

## Ownership

Bulletproof owns the deterministic quantitative decision producer and enforces its
receipt at external demo/live order-submission boundaries. The control plane owns only
the immutable schema registry, active-version gate, and custody of exact producer
receipts.

## Contract

- Every decision binds one immutable order shape to one causal state version.
- Exact RISK-002, RISK-003, RISK-004, EXEC-001, and EXEC-004 receipts are required.
- Stale state, missed deadlines, state races, partitions, unresolved incidents, failed
  reconciliation, and hard-limit violations fail closed.
- Degraded operation may authorize only a verified exposure-reducing order.
- Cancels and the independent emergency freeze/close path remain available.
- Neither the schema nor its receipts grant allocation, capital, order, or promotion
  authority.

## Evidence

The Bulletproof qualification fixture covers deterministic allow, deny, and reduce-only
outcomes. Broker-router tests prove external live submissions cannot reach an adapter
without a valid RISK-005 receipt. Control-plane tests prove registry immutability,
orchestrator protection, authoritative-producer enforcement, and active-schema binding.

The fixture is not evidence of candidate admission or a real exchange submission.
EXEC-006 must provide current upstream receipts and a fresh state snapshot for every
external order.
