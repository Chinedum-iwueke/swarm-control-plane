# DISC-004 Validation

- Five bounded planner methods operate only on compiled DISC-003 trial universes.
- Seeded proposals and adaptive rankings are deterministic under identical history.
- Fixed evaluation and batch budgets prevent unbounded search.
- Failures, cancellations and invalid trials consume budget and remain in history.
- Outcome-dependent early stopping is absent; completion requires the fixed budget.
- Event history is append-only, digest chained and replay verified.
- The service has no execution, result mutation, promotion, order, or capital authority.

## Production evidence

- VM2 migration head: `f9b3c6d85e20`.
- API rebuilt from merge `6c0473da0cb695f3d674010bca839158cc15b8e6` and reported healthy.
- Live Bayesian campaign: `64fa4499-4728-4db8-a1fd-570e503b075b`.
- Campaign specification digest: `d311f7fab9f702949b8f3ebbbb65c228e9a8a805f48b2b5e5e89e8f132d2fd2e`.
- Three proposed trials produced completed, failed, completed observations. All consumed budget and the campaign reached `complete` only after the third observation.
- Event chain verified under head `010acf94e119f18bf67ae7d9683465886bf2d210ab6c73013f40af224d28cef8`.
- Canonical report: `docs/evidence/disc004-report.json`; report digest `d2406f40e0f7b42ecbcecea5867c688fc9398fc0a863d8475c23d2e8a95e2922`.
- Regression validation: 500 backend tests and 16 focused tests passed.
