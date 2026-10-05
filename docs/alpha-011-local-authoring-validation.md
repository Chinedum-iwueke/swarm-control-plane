# ALPHA-011 Local-First Authoring Validation (Deferred)

> Production status: disabled. Active strategy-engineer units explicitly select
> `codex`; the installer removes this project's Ollama drop-in. The implementation is
> retained only for a future compute-backed requalification.

## Objective

Move repetitive hypothesis and native-strategy drafting to a CPU-local model without
letting that model certify itself, access credentials, widen scope or consume capital
authority. Keep Codex at the higher-value independent review boundary.

## Implemented controls

- Historical qualification used dedicated strategy engineers selecting `ollama`;
  production strategy engineers now select `codex` explicitly.
- The local endpoint must be loopback HTTP and the model receives no arbitrary shell
  or network tool.
- Reads and writes are confined to immutable contract paths; file count, diff size,
  tool output, context and turn budgets are enforced.
- Focused pytest runs use an allowlisted environment without worker or Codex secrets.
- The local author receives a typed compact evidence packet rather than the potentially
  48k-character control-plane record. It retains exact question, instruments, dataset
  identities, timeframe/resampling, representation plan, correction findings and
  authority boundaries plus SHA-256 custody digests for the complete evidence and
  acceptance contracts. Codex review and deterministic validation still receive the
  unabridged contracts.
- The local author must inspect its diff and run tests before finishing.
- Codex performs a separate read-only review; complete deterministic validation runs
  afterward; only then can a bundle be emitted.
- Ollama is bounded by systemd CPU, memory, swap, loaded-model and parallel-request
  limits so a model load cannot monopolize VM1.

## Model qualification

`qwen3-coder:30b` was rejected because it did not become ready under CPU-only
containment and an earlier unrestricted load coincided with a hard host reset.
`qwen2.5-coder:14b` was rejected for impractical latency. A standalone
`qwen2.5-coder:7b` qualification failed after it changed a frozen expected result
instead of repairing the producer; that result disqualified local self-certification,
not use of the model as a bounded draft author.

`qwen3:8b` passed the small bounded author fixture: it corrected addition semantics in the
allowed source, preserved the frozen test, inspected its diff and ran the focused
pytest successfully. Independent replay reported `1 passed`. The local policy digest
was `da8dbf5377611b3b3307aa795f1814d74e213f9f4b72fded61684f5be929fb7b` and the
summary digest was `b9258fc115ebc0b08ac83880bbfe5887d100bd39dce962b4cbacfc2eb1f22c2c`.
Its first production-parity attempt timed out before editing because the hosted-model
prompt was too verbose for CPU inference. `qwen2.5-coder:7b` produced bounded patches
promptly but missed frozen edge cases, establishing the conditional Codex-correction
requirement. The final route uses that coding-tuned 7B author, a concise immutable task
prompt, 8k context, 16 inference threads and capped tool-only turns. Hosted authoring
is not the default path; scoped hosted correction is invoked only when the retained
local focused tests fail.

## Application-level certification

The complete hybrid route passed the production-parity rehearsal outside the
root-owned service boundary:

- run ID: `cd4b4232-beb4-436c-bd64-b6db5838de3f`
- report digest: `6b203c8c8a490996589d1a5a5ea7d4c367465234756ec4aec46a86ff5ce260dd`
- local draft: bounded and retained, with a failed focused edge-case test
- scoped Codex correction: succeeded without widening writable paths
- independent Codex review: succeeded read-only
- compile and complete frozen test suite: succeeded
- lifecycle receipt: all 15 checks passed across eight bounded variants and a
  365-day synthetic window
- terminal receipt digest:
  `643d5d0fc790222dcd8f7748a25c83fa6ee4aab0a2904f54c79c51b2c0492fb3`

The rehearsal used no market data and conferred no order, capital, shadow or live
authority. It certifies orchestration and evidence retention, not alpha quality.

## Reopening gate

ALPHA-011 may be reopened only when suitable inference compute is available and the
installer runs the actual local-author, independent Codex review and full-validator
route inside the restricted systemd boundary. A fresh private production-parity report
is mandatory. The historical fixture does not establish alpha, production strategy
quality, promotion authority or capital authority.

As of 2026-10-05 the Ollama service is disabled and stopped, its loopback listener is
absent, and all five strategy-engineer consumers are explicitly pinned to `codex`.
The dormant implementation remains source-controlled so reopening requires an
intentional, reviewed deployment rather than an implicit provider fallback.
