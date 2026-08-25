# GOV-001 validation

GOV-001 is source-complete when:

- one digest-bound, versioned authority policy names canonical identities, roles,
  decision rights, scopes, risk ceilings, vetoes and separation rules;
- identity aliases resolve to the same principal and cannot evade independence;
- consequential task approvals through REST and Telegram produce immutable authority
  decision records before the task state changes;
- delegation is bounded by parent authority, environment, risk and a maximum 30-day
  expiry, while ambiguous active grants fail closed;
- exceptions require independent review, compensating controls and a maximum 24-hour
  expiry, and cannot waive constitutional boundaries;
- emergency authority can only halt, isolate, revoke, quarantine or reduce risk;
- policy replacement and rollback are themselves resolved under the active policy;
- Mission Control exposes the active policy digest and active delegation/exception
  counts; and
- migration, backend, Mission Control and JavaScript contract tests pass.

Production completion additionally requires migration `e6b1a4d82f90`, bootstrap of
the `invariance-institutional-authority` policy, a rebuilt VM2 API, an updated Mac
Mission Control installation, and one authorized plus one denied live decision replay.
Source validation must not be represented as that production replay.
