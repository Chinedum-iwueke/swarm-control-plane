# PORT-004 validation

Hermes registers the immutable PORT-004 schema and accepts only the exact authoritative
`bt.institutional.capacity.capacity_dossier_receipt` producer receipt. It does not
calculate turnover, cost, liquidity or capacity.

The cross-repository pilot requires exact schema and receipt replay, a qualified native
result, stressed capacity no greater than base capacity, stale-liquidity abstention and
an all-false authority boundary.
