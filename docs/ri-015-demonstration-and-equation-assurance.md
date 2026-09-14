# RI-015 Demonstration and Equation Assurance

## Changing RI-015 to demonstrated

RI-015 becomes `qualified`, not merely `contract_validated`, only after an
independent owner authors a hidden `live_corpus` suite at the current corpus,
retrieval and graph digests. The suite must cover all 13 domains and the declared
task classes with adjudicated gold answers. The real agent runtime must answer
without gold access; a different evaluator records citation entailment,
completeness, unsupported claims, abstention, formula/table accuracy, multi-hop
paths and latency. Every threshold and regression tolerance must pass. The
readiness endpoint then reports the exact qualified runtime and digest. Failures
remain visible and the state stays `not_qualified` or `not_demonstrated`.

The implementation already supports this contract. Remaining work is the
independent live suite and real-runtime response run, not a status override.

## Safe LLM equation use

An LLM can help locate, transcribe, parse and explain an equation, but agreement
with itself is not verification. ALPHA-004 therefore binds every located
expression to the source object, content digest and excerpt. Exact source replay
supports locating and explanation only; deterministic checks or an independent
adjudicator must produce an immutable receipt before an equation can drive a
campaign calculation. Unreadable, reconstructed or disputed notation remains
pending and cannot seed a campaign.

RI-014D now supplies this just-in-time assurance service. It combines exact
canonical source binding, two parser families, semantic-token equality, lossless
AST checks, cached immutable receipts and optional AGT-006-independent attempts.
Only consensus with replayable evidence issues a verification receipt;
disagreements remain visible as `needs_attention`. This improves usable coverage
without changing RI-015 to `qualified`: its independent hidden live-corpus
reasoning evaluation remains required.
