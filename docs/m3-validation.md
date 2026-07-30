# M3 Approvals and Artifacts Validation

Date: 2026-07-30

## Implemented Controls

- canonical immutable task-plan digest;
- pending, approved, rejected, revoked, expired, and consumed approval states;
- append-only approval events;
- random nonce with digest-only persistence;
- atomic approval consumption during leasing;
- fresh approval required after release or lease expiry;
- immutable artifact metadata and provenance;
- lease-authenticated worker artifact registration;
- restricted storage URI schemes;
- pre-terminal registration of complete step logs;
- protected operator inspection commands.

## Operational Gates

Production acceptance requires migration/API and worker deployment, then:

1. confirm an unapproved task cannot lease;
2. approve it and confirm exactly one lease consumes approval;
3. compare registered log digests with workspace files;
4. confirm release requires a fresh approval;
5. reject a separate task and confirm it never leases;
6. inspect approval and artifact events for secret-free bounded payloads.
