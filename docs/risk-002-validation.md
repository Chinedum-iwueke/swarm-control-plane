# RISK-002 validation

RISK-002 registers digest-bound venue rule evaluations against exact DATA-001 and admissible RISK-001 evidence. The server resolves the applicable margin tier and derives leverage, increment, mark-deviation, funding, maintenance-margin, equity, and liquidation-buffer checks.

Rules use observed, available, effective, and expiry clocks plus explicit active/suspended/retired transitions. Unknown, future, stale, inactive, expired, malformed, or breached rules fail closed. The receipt grants no allocation, order, or capital authority.

The live pilot is a deterministic control-path fixture, not a claim that its example limits are current Binance production limits.
