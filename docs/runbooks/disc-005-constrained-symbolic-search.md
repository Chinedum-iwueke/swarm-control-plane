# DISC-005 Constrained Symbolic and Program Search

DISC-005 accepts untrusted generator output only as data-only DISC-003 expression ASTs. It never executes generated code. A run requires an active AGT-004 policy with `output_authority=data_only`; only the read-only `research.retrieve` tool is permitted for evidence grounding.

Each run binds a base factor-program digest, prompt-policy digest, candidate budget, node/depth/constant limits, operator allowlist, required fields and parameter policy. Candidate output binds provider, model, version, seed, candidate index and canonical output digest.

Validation measures structure, rejects unapproved operators, missing fields, excessive complexity, digest drift and repeated generator identities that emit different output. It then invokes the DISC-003 causal/unit compiler. Commutative normalization detects reordered semantic duplicates against the base program and accepted candidates. Accepted, duplicate and rejected candidates all consume budget and remain retained.

Quarantine is a terminal run transition that preserves candidate lineage and records actor/reason. Nothing in this service executes trials, modifies results, promotes candidates, submits orders or holds capital authority.
