# RI-017 Validation

## Source evidence

- `approved_external_sources_v1.json` adds three immutable public-only definitions:
  statistical finance, machine-learning methods and Jane Street's public feed.
- `ri017_external_acquisition.py` rejects non-HTTPS, non-public, multiply allowlisted,
  private-address, oversized and unsafe-XML sources. It disables environment proxies and
  redirects, retries bounded transient failures and submits through the authenticated
  RI-006 API rather than writing canonical tables directly.
- The worker receives no cookies, browser profile, exchange credentials, code checkout
  write authority, LLM credentials or task-execution authority.
- Injection-like titles or abstracts remain rejected by RI-006 before publication.
  Retained metadata is a question seed only, never scientific or execution evidence.
- `alpha_discovery._recent_external_surveillance` supplies only sanitized title,
  provenance and deterministic assessment metadata to the next ALPHA-004 context.
  Abstract bodies are not placed in model context.

## Verification

- 79 focused backend discovery, external-policy and surveillance tests pass.
- 20 focused worker, systemd, utilization and skill-improvement tests pass.
- Ruff, shell syntax and diff hygiene pass.
- A read-only live connector smoke fetched 100 entries from each of the three new feeds.
  This is connectivity/parser evidence only; no production API state was mutated.

## Production evidence

VM1 runs the phase-one worker from exact control-plane commit
`6991b641bf6b14f03d9bad363a64f81d6b4f582b`. The first production pass retained five
successful fetch receipts and 499 immutable publications: 100 from each of three q-fin
feeds, 99 accepted and one rejected from the ML-method feed, and 100 from Jane Street.
The worker runs as `omenka` with no capabilities and receives root-owned API credentials
through systemd credential projection. Candidate metadata is available to the bounded
ALPHA-004 context and grants no canonical claim or execution authority.

Public YouTube transcripts, social observations,
NeurIPS/ICML proceedings and full-text adapters remain separate work because their
identity, rights, corrections and replay contracts are not yet complete.
