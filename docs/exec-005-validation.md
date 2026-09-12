# EXEC-005 validation

Hermes stores immutable execution-calibration schema identities and admits exact
Bulletproof producer receipts. It does not calculate fill, latency, shortfall, impact
or adverse-selection estimates.

The registry validates the canonical specification digest and makes name/version
identity immutable. Quantitative-receipt admission requires the authoritative
`bt.institutional.execution_calibration.execution_calibration_receipt` producer and an
active matching schema. Receipt/result digest verification and the existing all-false
authority envelope remain mandatory.

Focused tests cover registry replay, content and version drift, protected routes,
authoritative producer admission, missing active schema and no-order authority. The
cross-repository pilot registers the exact native specification and receipt, replays
both by ID, confirms qualified evidence and preserves sparse-evidence fallback.

Source qualification does not establish live venue calibration. Production activation
requires migration `f6b2d8a47e50`, rebuilt API deployment and exact replay of a sealed
native report.
