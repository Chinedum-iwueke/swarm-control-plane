# RI-014D Validation

RI-014D adds automated, just-in-time assurance for equations actually used by an
agent. Requests are immutable and cached by source-region digest, representation
digest, expression digest, policy version and required assurance level. Repeated
use does not reprocess the corpus.

The deterministic path requires exact source-object binding, lossless character
and semantic agreement from two parser families, a complete AST, accepted or
independently equivalent representation state and agreement across every output.
It issues a `machine_verified` receipt or fails closed as `abstained`. An
`independently_verified` receipt additionally requires an AGT-006 independence
receipt bound to the request cache key and an exact match to the independently
routed review digest. Provider labels alone confer no independence.

ALPHA-004 converts a replay-only equation to deterministically verified only when
this exact receipt is produced. It rejects missing, unrelated, weaker or invented
receipt digests. The calculation endpoint enforces the same receipt binding.
Mission Control exposes request state, assurance level, expression digest and
exceptions. Neither path grants shadow, order or capital authority.

Production closure requires migration/API deployment on VM2 and a successful
`python -m app.ri014d_pilot` run against a live accepted equation.
