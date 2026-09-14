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

Production closure was recorded on 2026-09-14. VM2 runs migration
`a0d6e8f92b51` and merged revision `504fb9ceea29d05cf571f2334cb74ccc6d9e5714`;
the rebuilt API was healthy with every ALPHA-004 and RI-014D route present.
`python -m app.ri014d_pilot` reused request
`1ee25d2d-af52-41f8-80cd-8bfea5742713`, rejected a mismatched expression and
issued `machine_verified` receipt
`441d4208430936b44830ebbf47dc8c21ca72a5ad5e355143e695b8de41f643b2`.
Its report digest is
`675ffd7409aedb864dd535272ff89b150ef9ce0a2e1afa65310d1ac7cf10ed4c`.
Mission Control was reinstalled from the same revision and verified running on
its configured loopback endpoint. This closes RI-014D; corpus-wide fidelity and
RI-015 reasoning qualification remain separate, honest gates.
