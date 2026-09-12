# DEMO-001 Bybit demo certification

DEMO-001 certifies production-like operational behavior on Bybit's demo service. It does not certify profitability and grants no live-order, capital, allocation, promotion, or scaling authority.

## Boundaries

- Bulletproof owns authentication, venue calls, dynamic instrument rules, order lifecycle, private events, reconciliation, safety drills, the evidence journal, and certification computation.
- Hermes stores the immutable contract and the exact Bulletproof receipt. It never receives exchange credentials and cannot recompute or widen the result.
- The REST endpoint must be `api-demo.bybit.com`; the private stream must be `stream-demo.bybit.com`; public market data may use Bybit's main public stream.
- Secret values and raw API keys are never written to the dossier. Only a one-way identity fingerprint is retained.
- Every run must end with zero open orders and zero position. Failure to prove the terminal state blocks certification.

## Required evidence

Venue-observed evidence is mandatory for authentication, server clock, current instrument rules, submission, fill, cancel, amend, rejection, private-stream reconnect, restart reconciliation, and final flattening. Partial-fill handling, duplicate suppression, stale-data rejection, runtime kill, and incident retention may use authenticated in-environment replay bound to the same run journal.

The runner derives quantity, price precision, and notional constraints from current `/v5/market/instruments-info` evidence. It must retain each venue response digest, typed failure, restart boundary, reconciliation result, and final flat-state proof. A missing or failed drill produces a blocked receipt rather than a partial certification.

## Rollback

Revoke or expire the DEMO-001 receipt, freeze submission locally, cancel demo orders, flatten demo positions under the separately authorized emergency path, and retain the complete dossier. LIVE-001 remains blocked independently.
