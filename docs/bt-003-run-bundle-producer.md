# BT-003 Hermes Run-Bundle Producer Contract

Hermes reuses `POST /v1/research/evidence/objects` for Bulletproof run bundles.
The canonical `run` payload accepts these optional fields as one indivisible reference:

- `bundle_digest`;
- `bundle_manifest_digest`;
- `bundle_uri`, formatted as `bundle://sha256/<bundle_digest>`.

If any field is supplied, all three are required and the URI digest must match. The
existing evidence service validates the canonical payload digest, immutable UUID,
aliases, dataset lineage and duplicate registration. An exact repeat returns the
existing record; an identity mutation returns conflict.

Legacy run records without a bundle reference remain valid. The API stores no bundle
bytes and receives no execution authority. Bundle storage and byte replay remain the
Bulletproof producer's responsibility.
