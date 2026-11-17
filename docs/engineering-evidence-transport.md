# Bounded, lossless engineering evidence transport

## Problem and boundary

Correction candidates retain their previous methods and rejection provenance.
Copying those records alongside the current representation, coverage and review
receipts can exceed the 48,000-byte engineering contract even when the scientific
contract is valid. This is a platform transport failure, not a scientific result.
It must not consume a scientific trial or rewrite the candidate.

## Contract

The backend contracts/engineering_evidence.py and its independently deployable
worker copy implement the same versioned codec. A parity test prevents drift.

- Existing JSON packets up to 48,000 bytes retain their original document shape.
- Larger packets use an engineering-evidence-zlib-v1 envelope carrying base64
  zlib bytes, expanded byte count and SHA-256 of the complete canonical JSON.
- The wire limit remains 48,000 bytes. Expansion is capped at 96,000 bytes before
  parsing. Decompression is bounded, not an unrestricted decompress-then-check.
- Both forms require an object with at most 20 top-level keys, depth at most 32,
  finite JSON numbers and no duplicate keys. Unknown versions, nested envelopes,
  trailing streams, incomplete streams and checksum/length mismatches fail closed.
- Preflight and task materialization use the same encoder. Coverage successors
  decode and re-encode through the same contract.

The hash provides integrity, not authority. Approval, candidate identity,
source pins, review receipts and scientific gates remain separate and unchanged.
No historical task is rewritten.

## Consumers

Worker policy and proposal validation inspect the expanded document but retain
the immutable wire contract. Author/reviewer prompts, native scaffold inputs and
retry evidence comparisons use decoded evidence. The scaffold artifact is normal
JSON with mode 0600; Bulletproof needs no new decoder or source transition.

This reduces transport duplication, not model token cost: models still receive
the complete evidence. It is not an excuse for unbounded context. Documents over
96 KB, or incompressible packets over the wire limit, remain explicit platform
blockers. A future artifact-backed evidence protocol would require its own
custody, availability and retrieval tests rather than silent truncation.

## Verification and rollout

Regression cases cover legacy inputs, 1/30/100-asset packets, exact round trips,
historical methods, tampering, expansion bombs, invalid JSON and native input
hydration. The retained BTC commissioning candidate replay was 55,192 expanded
bytes and 17,682 wire bytes with a bounded synthetic retrieval-size fixture;
every evidence field survived. This replay is a transport check, not a scientific
result or independent approval.

Deploy decoder-capable workers before enabling the API producer. Verify the API
and both director image identities together. Keep stopped engineering units
stopped until their governed work is eligible. Rollback to a pre-codec worker
requires draining compressed queued tasks or retaining decoder capability; do
not mutate their immutable contracts to make an older worker accept them.

SPX's discovery-abstention-to-method-correction authority path is a separate
unresolved issue. This transport change does not reinterpret its abstention as
an independent scientific rejection.
