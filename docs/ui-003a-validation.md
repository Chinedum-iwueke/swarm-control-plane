# UI-003A Citation-grounded Research Copilot

## Implemented boundary

Mission Control now provides a conversational Research Copilot above the canonical
RI-003/RI-008 interfaces. A question invokes authorized hybrid retrieval, bounded graph
context assembly and a read-only ephemeral Codex process. The model receives only the
context pack and a strict output schema. Raw source files, database access, operator
credentials, workflow execution and capital authority remain outside the boundary.

Answers expose claim-level evidence class, context-bound object citations, replayable
coordinates, retrieval confidence, explicit limitations, corpus/context/graph digests
and a terminal `insufficient_evidence` state. Retrieval abstention does not invoke the
model. A cited object outside the exact context pack rejects the complete answer.

## Founder experience

The Knowledge view is now a dense research workspace with a conversation thread,
bounded corpus selector, answer-confidence state, claim-level citation controls and a
dedicated evidence rail. Citation selection opens canonical identity, digest,
coordinates and exact replay. Existing Mac-local note search, inbox ingestion and the
bounded graph overview remain available below the Copilot.

The responsive layout was inspected at 1440 by 1100 and 390 by 844. It becomes a
single-column reading surface on mobile, retains visible labels and focus states, uses
44-pixel primary touch actions at narrow widths and honors reduced-motion preferences.

## Verification

- Mission Control compile: passed.
- Mission Control tests: 61 passed.
- Ruff: passed.
- JavaScript syntax: passed.
- Citation-outside-context rejection: passed.
- No-evidence abstention without model invocation: passed.
- Digest-bound cited-answer fixture: passed.

## Deployment gate

The Mac Mission Control installation must be refreshed after merge. Its protected
environment must point to an authenticated Codex home and installed Codex binary. A
live acceptance query must demonstrate retrieval, answer generation and exact citation
replay before UI-003A is described as production-observed.
