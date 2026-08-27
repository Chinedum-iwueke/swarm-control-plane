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

Pending deployment. Record the UI-004 pilot report digest, VM2 API health and Mac Mission Control installation after the source change lands.
