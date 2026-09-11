# EXEC-003 validation record

EXEC-003 adds the Hermes half of the explicit cross-venue identity boundary:

- migration `e4f8b2d05c30` and an immutable mapping-schema registry;
- authenticated create/list/replay routes;
- authoritative producer allowlisting for
  `bt.institutional.venue.venue_identity_receipt`;
- admission only when the receipt binds an active exact schema digest; and
- a cross-repository pilot that registers and exactly replays the native receipt.

The Bulletproof producer retains effective and availability clocks, explicit mapping
membership, compatibility blockers, venue health, contract conversion, venue-specific
increments, unmapped identities, and the no-authority boundary. Same symbols are never
treated as evidence of identity.

Source completion requires the focused Bulletproof and Hermes suites, their full
regression suites, Ruff, migration-head validation, deterministic native pilot, and
repository diff checks. Production completion additionally requires VM2 migration/API
deployment and an authenticated cross-repository replay. Until that replay exists,
the milestone is source-complete rather than production-qualified.
