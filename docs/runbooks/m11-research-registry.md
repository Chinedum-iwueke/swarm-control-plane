# M11 Immutable Research Registry

## Boundary

The registry records research; it does not execute arbitrary code, select a strategy,
or authorize trading. All writes require the orchestrator credential. Telegram may
display and request review decisions, but it cannot submit manifests or commands.

## Record Chain

```text
source snapshot -> hypothesis -> hypothesis approval -> experiment manifest
-> experiment approval -> trial -> result -> independent review -> decision
```

Specifications and manifests are canonical JSON documents. The client submits their
SHA-256 digest and the API recomputes it. Every downstream record binds the exact
upstream digest. PostgreSQL triggers reject every update and delete across all seven
registry tables, so correction means appending a replacement record.

An experiment cannot be registered until a reviewer other than the hypothesis author
approves the exact hypothesis digest. A trial cannot be registered until the exact
experiment manifest digest is approved. Results are one-per-trial and may be
accepted, rejected, failed, or inconclusive. All consume the declared family budget.
An executor cannot independently review its own result.

## API

- `POST /v1/research/sources`
- `POST /v1/research/hypotheses`
- `POST /v1/research/{hypothesis|experiment|result}/{id}/reviews`
- `POST /v1/research/experiments`
- `POST /v1/research/experiments/{id}/trials`
- `POST /v1/research/trials/{id}/results`
- `POST /v1/research/results/{id}/decisions`
- `GET /v1/research/hypotheses`
- `GET /v1/research/hypotheses/{id}/lineage`

## Pilot Gate

The first operational pilot must use a real completed research task and real artifact
digests. Do not invent evidence. Deploy migration `b2c4d6e8f110`, register the source
snapshot and predeclared M8 hypothesis, approve the hypothesis and experiment with
separate identities, register exactly one M8 run, retain its result regardless of
outcome, add an independent review, and record a final research decision.

Verification must prove that direct SQL `UPDATE` and `DELETE` operations fail, the
family trial count is one, lineage returns every record, and the original result
remains queryable.
