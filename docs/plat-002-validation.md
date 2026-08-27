# PLAT-002 Validation

PLAT-002 is complete when production evidence proves:

- every credential for an active package deployment binds an active workload identity;
- each identity binds the exact AGT-001 charter, package, machine, audience, owner, scopes and expiry;
- a valid scoped credential reaches an allowed endpoint;
- a confused-deputy request outside its scope is denied before handler execution;
- rotation rollback revokes the new credential and restores the prior scoped credential;
- secret-like request fields do not enter durable authorization receipts;
- privilege-expanding break-glass access is rejected;
- Mission Control reports identity presence and scope count per agent.

The deterministic backend suite covers scope derivation, strict schemas, separation of emergency duties and redacted receipts. The production pilot retains its digest-bound report at `/var/lib/invariance-swarm/plat002/report.json`.
