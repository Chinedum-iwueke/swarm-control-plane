# EXEC-002 validation

Bulletproof is the authoritative producer of market-microstructure state. Hermes
registers the immutable model contract and verifies producer receipts; it performs no
order-book, trade-formation, basis, funding, open-interest or liquidation calculation.

- Bulletproof merge: `adcbc0937befaf97ecefe4152b84e2cfa355abe4`
- Evidence-bound source: `e5754155250b858fceba6028ae1f6c0ffd2a020e`
- Hermes registry merge: `6c913021057a94ea15a6472d8fdde95b8b9d0f15`
- Migration: `f9d3e5b82a10`
- Native verification: 1,343 passed and 27 skipped; nine focused tests passed
- Hermes verification: 641 passed with two existing warnings
- Model ID: `59a5d26a-73f9-4fc0-afe1-4cfad67f28d2`
- Model digest: `27d73de1bba9dcf507dab8a9618b7f8384abf1851b75cc8d3a674249952fc23b`
- Receipt record: `708a844a-5023-4123-b934-8471acd01a70`
- Receipt digest: `1988100824f76b42c7efbe6267b489325a08af69490ab982d15b9f0e1648ace7`
- State digest: `808b035cde967608755aecc0ce48bb9ddf6f62c58194df22c2704aafc069bb99`
- Live evidence SHA-256: `62f53b3499aa03767d4056e475a9a5d997fe5173430ac7bdb82d23e749a43f0b`

The deterministic pilot reconstructed nine observed fields from validated EXEC-001
events and a valid DATA-003 dependency. Tests cover crossed books, missing levels,
venue resets, stale funding/open interest, receive-time cutoffs and inferred
liquidation proxies. Every field remains explicitly `observed`, `inferred` or
`unavailable`, with source event IDs, limitations and uncertainty.

This proves the typed calculation, dependency binding, immutable registration and
receipt replay for the fixture. It does not prove continuous live-exchange coverage,
microstructure alpha or production execution quality. No allocation, capital,
promotion or order authority was granted.

Rollback disables admission of the affected model version and retains its immutable
receipts. Consumers then use a previously active model version or abstain; Hermes
never rewrites historical states or substitutes unavailable fields with zero.
