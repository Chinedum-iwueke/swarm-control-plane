# ALPHA-009 Adaptive Multi-Asset Representation

ALPHA-009 certifies that the autonomous research loop can select a
hypothesis-specific basket and executable data representation before inspecting
targets or backtest outcomes. Historical `stable` and `volatile` labels are optional
metadata, not fixed universes. The researcher may use either group, mix them, or omit
the labels when the stated mechanism supports that choice.

## Contracts

1. DATA-002 catalog v1.1 exposes bounded per-instrument membership schedule summaries
   bound to the native stable and volatile manifest digests. These summaries carry no
   admission or execution authority.
2. The representation agent emits an `adaptive-representation-plan-v1.0.0` document
   with the ordered basket, member roles, arbitrary safe whole-minute/hour/day clock,
   complete-bar policy, typed transformation graph, rationale, rejected alternatives,
   and an explicit no-target selection boundary.
3. Bulletproof validates and replays the exact graph. Supported operations are
   identity, simple/log returns, train-only fractional differentiation with
   `0 < d < 0.5`, rolling z-score, realized volatility, spread, ratio, and
   cross-sectional rank.
4. Every selected panel remains separately content-admitted through DATA-002/003.
   Complete bars are left-closed and left-labeled, incomplete buckets are dropped,
   basket alignment is an inner join, and no future fill is permitted.
5. Compiled feature fields enter the engine panel only at `decision_at`. The reviewed
   strategy must bind the exact plan digest and declare the exact fields it consumes.
6. A native ALPHA-009 receipt remains `not_qualified` until three diverse reasoning
   cases replay and a mixed-basket terminal BT-009 outcome is retained. Negative,
   invalid, and failed terminal outcomes are valid operational evidence.

## Production Procedure

1. Publish and register the v1.1 manifest catalog from the reviewed Bulletproof
   commit.
2. Create a new weekly no-capital mandate bound to that catalog and source commit.
3. Retain three representation tasks covering cross-group transmission, persistent
   price-level memory, and local volatility/regime scaling.
4. Admit only the selected panels, engineer and independently review the exact native
   consumer, and run one bounded multi-asset BT-009 attempt.
5. Build `alpha009-adaptive-representation-certification-v1.0.0`, register it with
   Hermes, and verify every capability check is true.

No ALPHA-009 evidence grants shadow, order, promotion, or capital authority.
