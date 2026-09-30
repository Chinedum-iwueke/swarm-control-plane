# RI-017 Validation

## Source evidence

- `approved_external_sources_v1.json` adds immutable public-only definitions for
  statistical finance, machine-learning methods, Jane Street's public feed, the
  official Signals & Threads transcript index, official NeurIPS/ICML proceedings,
  one immutable-DID public Bluesky feed and Jane Street YouTube metadata.
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
- Migration `a7d4e9c21b60` widens the persisted feed-kind discriminator so every
  API-admitted connector kind fits the database contract. A model/schema regression
  prevents another accepted-value/persistence mismatch.

## Verification

- 166 focused backend discovery, campaign and surveillance tests pass.
- 35 focused worker mandate, contract, connector and systemd tests pass.
- Ruff, shell syntax and diff hygiene pass.
- A read-only live connector smoke fetched 100 entries from each of the three new feeds.
  This is connectivity/parser evidence only; no production API state was mutated.

## Production evidence

VM1 runs the worker from exact control-plane commit
`a147f2eb8b95df1d8f24d3d9d1809c0c32f5d455`. VM2 runs migration
`a7d4e9c21b60` and the API rebuilt from that commit. The production pass retained the
existing five bounded feeds and published 22 official Signals & Threads transcript
records without rejection. Its immutable fetch-receipt digest is
`fa445497989a4895c264ff3d0ff1b219c7f71836adbbb6c179381da8c5f3edb4`.

The worker runs as `omenka` with no capabilities and receives root-owned API credentials
through systemd credential projection. Retrieval and transcript extraction are
deterministic and do not invoke an LLM. Only sanitized title, provenance and assessment
metadata can later enter the bounded ALPHA-004 reasoning context as a question seed;
neither transcript text nor model commentary receives canonical claim, execution,
promotion, order or capital authority.

The expanded source set is source-complete but not yet production-qualified. A local
read-only smoke obtained records from the official NeurIPS and ICML proceedings, the
exact-DID public Bluesky author feed and Jane Street YouTube Atom metadata. This does
not replace production API receipts. Deployment must produce a v1.1 acquisition state
whose per-channel expected, successful and non-empty counts agree and whose status is
`qualified`. ArXiv timed out from the development host during the same smoke, so no
whole-registry operational claim is made yet.

Public YouTube transcripts and paper full text remain outside the implemented claim.
YouTube metadata, publisher abstracts and social observations are question seeds only.
