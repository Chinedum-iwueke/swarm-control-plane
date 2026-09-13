# EXEC-011 Validation

- Bulletproof focused suite: deterministic reordering, duplicates, corrections,
  missing sequences, reconciliation disagreement, secret rejection, episode replay,
  exact dependencies, and no-authority receipt.
- Control-plane focused suite: immutable schema, exact registered receipt binding,
  projection digest verification, redaction enforcement, idempotency, and protected
  routes.
- Mission Control focused suite: environment-labelled execution workspace, canonical
  projection client path, digest provenance, and no credential surface.
- Native pilot: nine-event Bybit demo fixture, exact reconciliation, duplicate
  suppression, and one completed trade episode.

Production acceptance still requires venue-observed Binance/Bybit private-stream,
restart, partial-fill, correction, and reconciliation drills on EXEC1. Fixture success
must not be represented as venue certification.
