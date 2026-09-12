# EXEC-008 validation

- Migration: `b5e1f8d37c40`
- Registry: `/v1/research/adapter-certification-schemas`
- Producer: `bt.institutional.adapter_certification.adapter_certification_receipt`
- Pilot: `worker/scripts/exec008_pilot.py`

The validation contract requires two exact Bulletproof receipts, one for Binance
perpetual demo and one for Bybit perpetual demo. The retained first pass is
deterministic conformance evidence only: `qualified`, `demo_execution_eligible`, and
`micro_live_eligible` must all remain false. Current venue-observed drills are deferred
to DEMO-001 and cannot be inferred from the fixture.
