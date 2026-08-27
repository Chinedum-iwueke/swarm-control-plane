# UI-004 Validation

## Contract evidence

- The approval center composes task, scope, prerequisite, mission, policy and notification state into one canonical review digest.
- A row lock and server-side recomputation prevent time-of-check/time-of-use approval races.
- Changed plans and stale review links fail closed with HTTP 409.
- Blocked gates cannot be approved.
- Decision receipts retain the reviewed digest and reason digest without storing secrets.
- Review links are read-only identifiers; they carry no authority.
- The legacy Telegram approval flow remains compatible.

## Automated evidence

- Backend approval-center tests cover current, contract-drift, stale-digest and receipt paths.
- Mission Control tests cover the displayed digest and outbound decision payload.
- The JavaScript bundle passes syntax validation.
- Full backend and Mission Control suites must pass before merge.

## Live evidence

Production acceptance completed on 2026-08-27 at merged source commit `6235b40f660624b41d4067ab3a462e3c273944f4`:

- VM2 rebuilt and recreated the API, which returned healthy with all three approval-center routes in OpenAPI.
- The exact approval-center projection returned 31 pending/recent records in 0.858 seconds after historical hydration was bounded.
- Mac Mission Control was reinstalled and its LaunchAgent recovered through a clean bootout/bootstrap; loopback status was healthy.
- Mission Control reported 16 historical pending gates, all 16 blocked and zero actionable, rather than presenting unsafe legacy approvals.
- The no-authority pilot rejected a deliberately stale digest, then retained rejection receipt `af6e654a27f3cb22aa0bb6913fb857965ac70317a8081ae4b52b36429e42cdcd` for current review `c8c414f5cbf88ab1a64d9b0198cbf3c41cdd4e4a6bfb5e36b73e632d23ee38bf`.

The canonical pilot evidence is `docs/evidence/ui004-report.json`, report digest `043859a3074955fe5b5b68ce21488ee6bd75606267705d08f438ad7c586f52a6`.
