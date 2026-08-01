# M13 Closed Five-Agent Pilot Validation

Status: implementation complete; production pilot pending.

## Implemented

- Five distinct role packages, permission profiles, capabilities, and agent identities.
- Agent-authenticated research proposal, specification, result, and review endpoints.
- Active-package and capability checks at every role endpoint.
- Immutable data-snapshot registry linked to experiment manifests.
- A digest-bound 8,760-row real Binance BTCUSDT hourly snapshot.
- Restricted real-data signal execution in the existing isolated Git worktree.
- Founder approval before execution.
- Separate statistical reproduction and adversarial audit identities.
- Two distinct reviews required before a founder decision.
- Complete positive or negative trial retention and related-hypothesis search.
- Production eligibility fixed to false.

## Automated verification

- Backend: 64 tests passed.
- Worker: 171 tests passed.
- All five local role packages and workflow digests validated.
- Ruff, compileall, and diff checks pending final run.

## Production evidence

Populate after deployment and pilot:

- source commit:
- migration head:
- five agent, package, and deployment IDs:
- snapshot ID and digest:
- brief, hypothesis, experiment, trial, and task IDs:
- founder approval ID and plan digest:
- task event sequence and attempt count:
- result outcome and digest:
- statistical and adversarial review IDs:
- exact reproduction result:
- founder decision:
- related-hypothesis search count:
- retained workspace and artifact digests:

## Exit decision

M13 exits only when the founder-approved real-data trial is executed once, independently
reproduced, adversarially reviewed, retained regardless of outcome, and searchable.
