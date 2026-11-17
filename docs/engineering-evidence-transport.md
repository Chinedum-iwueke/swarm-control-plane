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
- The wire limit remains 48,000 bytes. Ordinary evidence remains capped at
  96,000 expanded bytes. Accepted-method handoffs may use the bounded artifact
  extension described below. Decompression is bounded before parsing.
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

Ordinary evidence remains inline. Incompressible packets over the wire limit
remain explicit platform blockers. No context is silently truncated.

### Accepted-method artifact extension

An accepted-method packet can retain a substantial immutable review history.
The `engineering-evidence-xz-v1` envelope supports up to 262,144 expanded bytes
only for the accepted-method handoff shape, still within the 48,000-byte wire
limit. XZ decoding has a 32 MiB memory bound and bounded output; shape does not
confer authority. The worker independently verifies source, plans, both reviews
and the contract binding before writing the evidence artifact.

For oversized handoffs, the prompt retains the current proposal, requirements,
native plan report and all other top-level engineering evidence. This active
view must fit 96,000 bytes. Full history, dependencies and review records remain
in `../artifacts/accepted-method-evidence.json`, with its canonical SHA-256 in
the prompt. Author and reviewer are instructed to read that file. It is written
before model work, mode 0600, and checked for modification before every episode
stage and on retry. Native scaffold inputs still receive the complete document.
This enables tool-mediated reading; it does not prove a model read every item.

A read-only sizing probe using the real accepted BTC packet and new ready native
plans measured 174,410 original bytes, 33,237 wire bytes and 88,137 prompt bytes.
Every original field round-tripped. This probe used no new review verdict and
does not constitute an authorized or scientifically accepted handoff. Final
registered reviews still need their own complete-contract preflight.

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

## Live checkpoint, 2026-11-17

Release dd50976 was pushed to main and deployed. VM1's engineering interpreter
loads the decoder; stopped engineering units were not started. The API and both
directors passed image parity and API health verification.

Supported reconciliation of campaign fe25230c-088e-44c0-84ac-98d97ca86739 cleared
the context-size blocker without changing its candidate or mandate. Requirements
publication 70899 created route e0065f3b-5bf2-4a28-9d58-7f07479ef090.
The strategy-spec and causality-leakage review tasks were both observed running
on attempt 1. No engineering or backtest completion is inferred from this.
