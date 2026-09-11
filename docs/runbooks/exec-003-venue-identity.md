# EXEC-003 venue identity and fragmentation

## Boundary

Bulletproof is the sole quantitative producer. It consumes immutable DATA-001
instrument revisions plus EXEC-001/002 receipts and emits an effective-dated venue
identity dossier. Hermes stores the admitted mapping schema and verifies the exact
producer receipt. Hermes does not infer equivalence, convert contracts, route orders,
or calculate consolidated market state.

An explicit relationship means economic comparison or hedge substitution only. It
never means positions are operationally fungible between venues. Every route keeps
the source and target venue, listing, settlement, margin, contract multiplier, tick,
quantity, notional, lifecycle, health, and observation clocks visible.

## Fail-closed rules

- Symbols never establish identity.
- Mapping and instrument revisions are effective-dated and availability-dated.
- Inactive, delisted, unavailable, or unknown members quarantine the mapping.
- Incompatible base, type, quote, settlement, margin, inverse convention, or expiry
  quarantines an economic-equivalence mapping.
- Stale venue health is treated as an outage.
- A venue outage blocks comparison routes without rewriting identity history.
- A listing cannot belong to two active relationship groups.
- The receipt grants no allocation, capital, order, promotion, or routing authority.

## Production replay

1. Run `scripts/exec003_pilot.py` in `bulletproof_bt` with the exact full source
   commit and retain the native report outside the checkout.
2. Deploy migration `e4f8b2d05c30` and the rebuilt API.
3. Run `worker/scripts/exec003_pilot.py --native-report ... --output ...` with the
   root-owned pilot operator environment.
4. Verify that the schema and quantitative receipt replay with the same digests.

The pilot is deterministic contract evidence. It does not certify a live adapter,
venue connectivity, account, demo environment, or order path; those remain
EXEC-004 through EXEC-008 and DEMO-001.

## Rollback

Stop admitting the affected mapping schema version and pin its prior active version.
Preserve every registry row and producer receipt. Quarantined or unknown mappings must
remain unavailable rather than falling back to symbol equality.
