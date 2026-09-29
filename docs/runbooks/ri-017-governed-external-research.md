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

The isolated VM1 public-feed worker, expanded immutable source registry and hardened
six-hour timer are implemented. It submits to the existing RI-006 source, fetch,
publication, correction/retraction, digest and Mission Control surfaces. The initial
registry adds statistical-finance and ML-method arXiv feeds plus Jane Street's official
public feed. A bounded exact-host HTML adapter also retrieves the official Signals &
Threads transcript pages, strips page chrome, caps per-page and aggregate bytes and
submits transcript text through the same quarantine. It does not call an LLM and does
not grant network access to existing ALPHA-004 Codex services.

RI-017 remains operationally open until the transcript adapter's exact commit is
deployed and representative fetch/replay receipts are observed. Public YouTube
transcripts, social sources, NeurIPS/ICML proceedings adapters and paper full text
require separate exact-source, rights,
correction and parser contracts; Agent Reach availability alone is not admission.

Install on VM1 only after the reviewed commit is present:

```bash
sudo bash worker/systemd/install-ri017-external-acquisition.sh <exact-control-plane-commit>
```
