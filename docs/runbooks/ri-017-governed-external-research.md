# RI-017 Governed External Research Acquisition

## Purpose

RI-017 broadens RI-006 beyond the current arXiv q-fin feeds. An isolated retrieval
worker may collect public scholarly metadata, journal/RSS items, public YouTube or
podcast transcripts and low-trust social observations. It produces immutable fetch and
content receipts for canonical admission; it does not place raw internet text directly
inside a reasoning agent's trusted context.

## Source and trust classes

- Scholarly metadata and abstracts can become admission candidates, but publication is
  not correctness and abstracts are not full-method evidence.
- Public transcripts can seed claims only with exact source replay and transcription
  uncertainty. They cannot verify equations or quantitative conclusions.
- Social content is `observation_only`. It may seed a falsifiable question but cannot
  support a scientific claim, code change, promotion or execution decision.
- Instruction-like content is quarantined before canonical retrieval.

Every request requires HTTPS, an exact host allowlist, public unauthenticated access,
declared rights, connector identity, pinned provider commit and a content digest.
Cookies, browser-session import, account login, arbitrary shell, system-package
installation and automatic canonical admission are forbidden in the first phase.

## Agent Reach integration boundary

Agent Reach is audited as a connector-coverage and health-diagnostic reference, not as
a privileged research runtime. The pinned phase-one policy enables only public web,
RSS, scholarly-metadata and public-transcript adapters. The upstream installer and its
credentialed/social/browser-cookie paths do not run inside senior-researcher units.

The senior researcher receives only independently admitted, sanitized evidence packs.
Retrieved instructions have no tool authority. New sources require curator approval;
the source registry, rights and allowlist are immutable once used by a receipt.

## Closure

Source policy and quarantine tests are present. RI-017 remains open until an isolated
worker, source registry, immutable storage, correction/retraction path, Mission Control
queue and production fetch/replay receipts are deployed. This source slice grants no
network access to existing ALPHA-004 Codex services.

