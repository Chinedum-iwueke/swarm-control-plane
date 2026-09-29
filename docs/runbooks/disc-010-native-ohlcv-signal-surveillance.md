# DISC-010 Native OHLCV Signal Surveillance

## Purpose and ownership

DISC-010 continuously searches admitted OHLCV panels for reproducible observations
that deserve governed hypotheses. Bulletproof owns every market-derived calculation.
Hermes schedules bounded families, validates signed receipts and routes accepted
observations into DISC-002/003/009; it does not become a second quantitative engine.

## Search families

The initial registry should cover, without privileging any one result:

- serial dependence, reversal, continuation and calendar structure;
- cross-asset lead/lag and conditional dependence;
- correlation, beta and residual-distribution shifts;
- volatility, volume, liquidity and tail anomalies;
- change points, clustering and persistence;
- cross-sectional dispersion and concentration;
- representation comparisons such as causal aggregation, returns, scale normalization
  and train-fitted fractional differentiation.

Each family declares admissible instruments, point-in-time membership, predictor and
target clocks, transformations, missing-data behavior, cost proxy, search budget and
null. Stable/volatile labels are optional metadata, not hard universe boundaries.

## Outcome separation

Universe and representation selection use metadata and predictor history only. Search
uses exploration/training partitions with purging, embargo and a complete family
ledger. A separate validation partition tests stability. The final OOS partition is
sealed and can be opened only by the registered evaluation. Multiple-testing and
selection-bias corrections apply across all attempted transforms, horizons, assets and
subgroups, including failed and duplicated trials.

The output is an immutable observation and candidate question with support, effect,
uncertainty, costs, stability, falsifiers and complete trial lineage. It is not a
strategy, alpha claim or promotion. Surviving questions still pass mechanism review,
strategy engineering, independent review and BT-009.

## Relationship to ML

The first pass uses transparent statistical baselines. ML-002 materializes causal
features, labels and splits only after a signal/state contract exists. ML-003 compares
registered model families against unconditional and linear baselines; ML-004 calibrates
uncertainty and abstention. Nonlinear mining is a later bounded family, not permission
to search the sealed OOS set.

## Closure

Bulletproof already contains representation, discovery, state-analysis, correlation
and candidate-ranking components, but they are not yet one continuously scheduled,
universe-wide receipt producer. DISC-010 remains open until that producer, its complete
search ledger, synthetic null/leakage tests, cross-asset replay and production receipts
are demonstrated.

