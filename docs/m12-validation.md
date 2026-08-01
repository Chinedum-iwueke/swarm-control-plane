# M12 Research Knowledge Foundation Validation

Status: complete.

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

- source commit deployed and synchronized: `a75ff97`;
- production migration head: `d4e6f8a0b220`;
- VM2 API health: healthy;
- registered documents: `4`;
- registered immutable passages: `60`;
- append-only knowledge-table triggers: `4`;
- corpus digest:
  `45b5e0454dc22f1ffbdd9a44e63930af0998320e5c6603b974de578312cea6f6`;
- evaluation: `eb7f88cd-da50-4cbf-8ad5-613b7ddc66aa`;
- evaluation record digest:
  `1ad06062d3002aea083b93e47307a98d8d711a3a8ec97e33951d81c351ee0e21`;
- fixed questions passed: `3/3`, recall `1.0`, required recall `1.0`;
- question-set digest:
  `d4216e743f6b5c43d078943f9846c3aecf7eb409cd10e765b7a4f7f2b20ad19d`;
- brief: `158b0630-aff6-423c-8982-9204fbd50c22`;
- brief digest:
  `da68ff504d93aac050d9ff7f0c0babbfd16804f4529e91b1fda9733a857d5764`;
- governing citation passage: `b4c679fb-d678-4822-ab02-424f63c7b92d`,
  PRD page 5, lines 180-244, passage digest
  `a0a863242a0ade191dc58296f305fca27e6eb5b14f84355e85c0df208658d579`;
- prior-result citation passage: `9a71480c-388e-45a5-bc38-6816bafd9308`,
  M11 `Operational Pilot`, lines 45-72, passage digest
  `c48622a8e8414fa53621a31d7a03e3a8fed1944bf585e7aa0c15dd06e650a318`;
- the third claim is explicitly classified `agent_inference` and has no citation;
- the governing and prior-result searches resolved against the same corpus digest.

Similar-hypothesis and prior-failure retrieval are implemented over the M11 registry.
The exit question was about governance rather than the registered momentum hypothesis,
so both related-record lists were correctly empty. The production registry currently has
no negative M11 trial result to return as a prior failure; negative-result retrieval must be
revalidated when the first such result is registered.

## Exit decision

M12 has reached its exit gate. The production pilot produced a corpus-bound brief whose
two material source claims resolve to immutable passages and whose analytical extension
is explicitly labeled as agent inference. The knowledge service remains proposal-disabled
outside this evaluated brief path; M13 must preserve that boundary while adding agents.
