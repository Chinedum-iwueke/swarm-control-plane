# M12 Research Knowledge Foundation Validation

Status: implementation complete; production pilot pending deployment.

## Implemented controls

- Immutable document, passage, retrieval-evaluation, and brief records.
- SHA-256 binding at document, passage, corpus, question-set, evaluation, and brief level.
- Exact PDF page citations and exact Markdown section/line citations.
- Strict evidence classification and claim-source links.
- Explicit `agent_inference` labeling for uncited analysis.
- Deterministic lexical plus structured retrieval.
- Similar-hypothesis and prior-failure lookup over the immutable M11 registry.
- A passing fixed evaluation for the current corpus is required before brief creation.
- PostgreSQL full-text index for bounded future corpus growth.

## Initial corpus

- Invariance Agentic Systematic Trading Firm PRD PDF.
- M8 research validation report.
- M11 research registry validation report.
- M11 research registry runbook.

Licensed statistics and time-series texts and founder-approved papers remain an explicit
post-M12 corpus expansion. They are not silently substituted with model memory or
unverified excerpts.

## Local verification

- Backend tests: 63 passed.
- Worker tests: 169 passed.
- Compile and Ruff verification: passed.

## Production evidence

Populate after the VM2 migration and VM1 pilot:

- source commit:
- production migration head:
- corpus digest:
- evaluation id and recall:
- brief id and digest:
- cited passage ids:
- similar-hypothesis count:
- prior-failure count:

## Exit decision

M12 reaches its exit gate only after the production pilot produces a brief whose material
claims resolve to immutable source passages or are explicitly labeled as agent inference.
