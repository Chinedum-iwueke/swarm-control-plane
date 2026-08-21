# RI-010 Memory Lifecycle Validation

RI-010 adds governed lifecycle semantics to canonical institutional memory. It
does not delete history silently and it does not give a model retention
authority.

## Contract

- Every canonical evidence object has one materialized lifecycle state.
- Active evidence can be consolidated, superseded, corrected, retracted,
  expired through explicit decay, or restored from a reversible state.
- Consolidation requires equal content digests and emits an immutable receipt.
- Registering a declared canonical successor automatically marks the prior
  object superseded in the same transaction.
- Retention holds name their authority and reason and block deletion.
- Lawful deletion requires a request with legal basis and a different approving
  authority. It removes the protected JSON payload while preserving a
  non-sensitive tombstone, original payload digest, canonical content digest,
  lineage, audit event, and dependency impact report.
- Deleted, consolidated, superseded, retracted, and expired objects are excluded
  from active graph and retrieval projection builds.
- Lifecycle state changes advance the canonical freshness epoch. Retrieval and
  graph queries therefore fail closed until their derived projections rebuild.
- Frozen dossiers are never rewritten. Replay reports lifecycle impacts and the
  successor identity where one exists.

## Operator surface

The authenticated lifecycle API exposes state listing, object dossiers, typed
actions, retention holds, deletion requests, and independent deletion decisions.
Mission Control lists non-active memory and opens its immutable lifecycle and
impact dossier. Mutations remain protected by the founder-intent header and the
control-plane orchestrator credential.

## Verification

- Backend full suite: 260 passed before production deployment.
- Mission Control suite: 45 passed.
- Focused lifecycle, retrieval, graph, and dossier suite: 87 passed.
- Ruff and compileall: passed for changed surfaces.
- Alembic head: `a4e7c9d21f60`.
- Control-plane merges: PR 54 (`63855851677b8b0ec0cd9a20159bf45e70bcfaa8`)
  and pilot response fix PR 55 (`ada05ecf86123c7aed9a820e96e586e8279079a1`).

## Clean-room pilot

On 2026-08-21 the entire migration chain was applied from an empty PostgreSQL
17 database to `a4e7c9d21f60`. A live loopback API then executed the production
pilot through its authenticated HTTP routes. All checks passed:

- duplicate consolidation with equal canonical content digests;
- automatic supersession propagation when a corrected successor registered;
- retraction followed by authorized restoration;
- retention hold rejection of an independently approved deletion;
- hold release and independently approved lawful deletion;
- terminal deletion state with payload tombstone and retained lifecycle dossier;
- stale retrieval and graph detection followed by successful rebuild;
- active graph contained only the two surviving active objects.

The consolidation, supersession, retraction, restoration, retention and deletion
dossier digests were respectively:

```text
a49c6933dcc947118fcd439c0b8ecebc16f357f1234957907d3c31dbc8157288
a1b802d99f94ed472b84d383981c2f54f4447aafec6efb17e945908d5856bf5c
c28f3ae8112a93e8cf2f0d6e7a6c787781506fd7123d02d6844b0a6a9abbf6e3
3ca620f47b55636a55356649627aed0c196a5a39012577269866c400ab01325f
32b29ef5f1d14a1b7e3e12fb9f9c1361211fdd96c7b7db0efa4d5f8723e7caef
c56bbe3e756f1633580755358745a35f2cb518d09fad5917a96ac63d1d37b06f
```

The Mac pulled `ada05ecf86123c7aed9a820e96e586e8279079a1`, reinstalled
Mission Control, and returned a healthy loopback status. Its lifecycle ledger UI
is ready for production lifecycle records.

## Production activation

On 2026-08-21 VM2 returned online. Its clean `main` checkout fast-forwarded to
validation merge `7085872e1d598d5afbf876c762d4d60ed27f05c3`; the API image
rebuilt, the production database migrated from `c8f2a6d94e31` to
`a4e7c9d21f60`, and the recreated API became healthy.

The founder then ran the exact authenticated production pilot under the
root-protected operator environment. All eight lifecycle checks passed. The live
dossier digests were:

```text
consolidation  2cac7f71b8bba053b884707fccced0d50a2b4b0d8dc7f4ff5049122635969642
supersession   dbaeb3a8295216df995c0ad0f869d51e497097faa610a36ee8a033155009d7af
retraction     03d3767ae4bb91a258671311ce0a2448ab7e94452bc61a65501b6ffffc39e5b2
restore        098ba240a27459defa855eafcef1c129abf9a905ed1aa788ee6af32b64dc4a7b
retention      dc5b9fa291fe57f6d082682d3f2abc986b1c0175283b3df9e36266667055d8a8
deletion       19d70b27e74456ffa23d5fc04a07fa44549a5eb73f36eca4fbbb1439e9433a38
```

Retrieval rebuilt current with 623,375 objects at source epoch 25 and manifest
digest `f3e07bc8e94164055d3616759c992b64610a7073472a65021e465ad0472e6883`.
The graph rebuilt current with 623,731 nodes, 1,097,688 edges and manifest digest
`ceab189ceccd4b99067af0e42721fb4abdb9880c941607f340470a73ec57b334`.
RI-010 is production-qualified for the exercised VM2 version and environment.

Rollback restores the prior API image; lifecycle tables
are append-oriented and should be retained unless the migration has never
accepted a lifecycle transition.
