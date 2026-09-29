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

## Native source and scheduling

Bulletproof PR 353 implements the authoritative producer, content-bound CLI,
capacity-queue adapter and manifest-only replenisher. The producer supports arbitrary
safe minute/hour/day aggregation above the native one-minute panels, cross-asset
lead/lag families, train-fitted fractional differentiation, empirical circular-shift
nulls, whole-family correction and a complete invalid/null/survivor ledger.

The replenisher inspects DATA-002 coverage metadata only. It rotates three-asset
baskets across every quality-visible Bybit perpetual panel with sufficient overlap;
stable/volatile group labels are not selection constraints. It maintains at most
three active fallback screens, six workers each under the current memory estimate,
at queue priority 10. Approved BT-009 assignments retain priority 50. The scientific
receipt is invariant to one-versus-eight worker execution.

Each trial ledger entry retains its complete preregistered contract as well as the
contract digest. Hermes recalculates that digest before registration. The VM1
publisher scans only atomically completed `receipt.json` files, recovers registrations
already present in Hermes, and maintains a mode-0600 local publication ledger. It does
not publish partial output or grant strategy authority.

Registered screens are projected into the next ALPHA-004 bounded context. Both
survivors and null/invalid trials are included so the senior researcher can formulate
or reject a new hypothesis without repeating the same search. A screen survivor is
still only a question: normal novelty, timing, data admission, engineering,
independent-review and sealed-OOS gates remain mandatory.

Production uses a code-only Bulletproof checkout and a separate persistent lake. The
service therefore pins both the exact code commit and an explicit read-only data root.
It never assumes that a Git worktree owns the lake.

Install after both merged checkouts are at the exact reviewed commits:

```bash
sudo bash worker/systemd/install-disc010-replenisher.sh \
  <exact-control-plane-commit> \
  <exact-bulletproof-commit>
```

The installer enables separate replenishment and publication timers. Mission Control
shows registered families, evaluated/invalid trials, candidate questions and their
closed-authority boundary under **Research -> Signal surveillance ledger**.

## Closure

The source producer and queue/replenishment seam are implemented and locally verified.
DISC-010 remains operationally open until Bulletproof PR 353 and control-plane PR 400
land, the pinned services are deployed on VM1, the rebuilt API and Mission Control are
deployed, at least two concurrent real-lake screens terminate, their receipts are
registered through Hermes, and an accepted question (or an honest null family) is
visible in Mission Control. Source completion is not production certification.
