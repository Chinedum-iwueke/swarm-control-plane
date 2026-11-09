# ALPHA-013 Copilot Hybrid Strategy Authoring

## Decision

Native strategy engineering uses GitHub Copilot CLI as the first author and Codex as
the corrective and independent-review authority. Deterministic code owns feasibility,
the immutable `StrategyIntent`, scaffolding, focused tests, the complete Bulletproof
suite and BT-009 publication. The dormant CPU-local author is not selected.

The route is:

```text
research question
  -> deterministic feasibility preflight
  -> immutable typed StrategyIntent
  -> deterministic scaffold
  -> bounded Copilot implementation
  -> deterministic scaffold and focused-test checks
  -> Codex correction only when focused tests fail
  -> independent read-only Codex review
  -> complete Bulletproof validation
  -> evidence bundle and BT-009 handoff
```

## Authority boundary

Copilot receives only `view`, `rg`, `glob` and `apply_patch`. Shell, web tools,
built-in MCP servers, repository instructions, interactive questions and automatic
CLI updates are disabled. Global path approval remains disabled, so file access stays
subject to Copilot's path verification inside the trusted disposable working folder.
That folder is created from the pinned internal repository, while custom instructions
and MCP tools remain disabled.
The CLI boundary makes exactly those four tools available before inference.
Activation pins Copilot CLI 1.0.105, and every authoring receipt must independently
attest the same four tools. Any missing or newly introduced tool fails the mission.

## Qualification evidence

The restricted production-systemd rehearsal completed on 2026-11-05 with report
digest `ca348270c05eaf77f52d4d501c65401b1bf0b31e728a5be4ff543f33cd15df34`.
After global path approval and the open-ended tool grant were removed, a fresh
bounded rehearsal completed on 2026-11-09 with report digest
`c972634b810edfeb3019706256fab25fee98336d51bc9f0fbed04becfa5d5879`.
Copilot was the effective author with no fallback, the independent Codex review
approved, deterministic compilation and tests passed, all lifecycle checks passed,
and the synthetic BT-009 receipt retained all eight terminal variants without
market-data, production, order or capital authority. The singleton plus replicas
`@2` through `@5` were then activated, yielding five concurrent governed strategy
engineering workers.
The trusted workspace makes in-repository authoring non-interactive without granting
global path access. The process also runs inside the systemd filesystem jail and a
disposable Git worktree. After the model exits, the worker independently rejects any
path or diff outside the approved task contract and verifies that the typed intent
digest did not change.

Copilot is not a scientific evaluator and cannot approve its own output. It cannot
run tests, change the immutable hypothesis contract, push, merge, deploy, submit
orders or grant capital authority.

## Fallback policy

Codex fallback is allowed only for an objectively classified Copilot infrastructure
failure: authentication, quota/capacity, provider/network outage, timeout or process
launch failure. A normal nonzero exit, malformed implementation, failed focused test
or independent-review rejection is not provider-shopping authority. Failed focused
tests may receive one Codex correction pass against the same immutable contract.

Every attempt retains:

- Copilot JSONL stdout and stderr logs;
- `copilot-author-result.json` with the selected model and session identifier;
- `copilot-author-usage.json` with provider accounting;
- `author-provider-route.json` with requested/effective provider and fallback reason;
- deterministic test, review, patch and PR-bundle evidence.

## Production activation

The production binary is fixed at `/usr/local/bin/copilot`; the dedicated state path
is `/var/lib/invariance-swarm/copilot-author-runtime`. The idempotent installer runs a
no-capital production-parity rehearsal before starting any strategy-engineer replica.
The installer seeds the private runtime from a user-owned, device-authenticated
credential staging directory at
`~/.local/state/invariance-swarm/copilot-hybrid-runtime` without printing or
committing its credential. The rehearsal is the authentication and integration
proof. If authentication is missing or expired, run the documented device login as
`omenka`, then rerun the installer.

Unit qualification covers configuration wiring, tool confinement, semantic
no-fallback behavior, infrastructure fallback and systemd boundaries. Production
qualification additionally requires the installer rehearsal to pass in the deployed
systemd boundary. No rehearsal result is trading or capital authority.
