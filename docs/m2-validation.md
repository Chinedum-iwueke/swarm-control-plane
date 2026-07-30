# M2 Versioned Role Packages Validation

Date: 2026-07-30

## Implemented

- strict role-package schema with forbidden unknown fields;
- immutable package name/version and canonical manifest digest;
- HMAC-SHA256 registration signature verification;
- source repository and commit provenance;
- workflow registry entries with exact local YAML digests;
- worker semantic compatibility bounds;
- capability, machine, risk, permission, and repository profiles;
- agent deployment inventory and explicit revocation;
- heartbeat package name, version, and digest evidence;
- operator registration and inventory tool.

## Safety Properties

- manifests contain no command field;
- registry responses never become subprocess input;
- workflow files remain local and allowlisted;
- digest or compatibility mismatch fails before heartbeat and leasing;
- restricted profiles forbid privilege, primary-checkout writes, and remote
  repository writes;
- signing and orchestrator secrets are not printed.

Production acceptance requires migration/API deployment, package registration,
agent binding, worker `check`, inventory inspection, and one supervised task
whose heartbeat records the registered package digest.
