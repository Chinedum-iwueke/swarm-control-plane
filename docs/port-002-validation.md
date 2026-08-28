# PORT-002 live validation

Date: 2026-08-28

## Ownership

Bulletproof merge `79caf1d334a5e80d03cf644875dfa022d09c952a` owns the
dependency, diversification and concentration calculation. Control-plane merge
`3a2a38ba15d455263281c42d06881d7aebc601d0` adds only the authoritative
producer allowlist to the existing immutable receipt registry. Replay merge
`0b30fd81eeb80ec85bfacc45fd076728a8837c0f` makes the bridge batch-agnostic.

## Live replay

VM2 ran the rebuilt healthy API and registered PORT-002 receipt
`70f4ff8045875341e8f324cd2a1f44ff22a309d4dc0362c011b5a51a1c5138be`.
The receipt was read back exactly as record
`5c55f791-227a-4c40-a86a-301eec866b9e`.

Retained evidence: `docs/evidence/port-002/live-replay.json` with SHA-256
`6b4a7692bb7a0846e4406f407d42ef0e43cc8d7e5437277754b1968aab61e40d`.

The replay grants no allocation, capital, order or promotion authority. The
deterministic fixture proves the service contract and repository boundary, not
market alpha or production portfolio fitness.
