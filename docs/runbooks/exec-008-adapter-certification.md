# EXEC-008 adapter certification

## Ownership

Bulletproof declares venue capabilities, evaluates drill evidence, assigns expiry,
and emits the authoritative producer receipt. Hermes registers the immutable schema
and retains the exact receipt. Hermes does not recompute certification.

## Deployment

Deploy migration `b5e1f8d37c40`, rebuild the API, and run the cross-repository pilot
with a native Bulletproof report.

```bash
worker/.venv/bin/python worker/scripts/exec008_pilot.py \
  --native-report /var/lib/invariance-swarm/exec008/native-report.json \
  --output /var/lib/invariance-swarm/exec008/report.json
```

The first production replay is intentionally `conformance_only`. It demonstrates
that deterministic response fixtures cannot grant demo execution or micro-live
eligibility.

## Venue-observed certification

DEMO-001 must execute the same required drills against each named venue demo endpoint,
retain protected raw references outside Hermes, and publish only bounded evidence and
digests. A certification is valid only for its venue, product, environment, adapter
source commit, observed interval, and expiry. Any failed drill, mismatch, revocation,
or expiry blocks admission.

## Rollback

Restore the previous API image if registry deployment fails. Do not delete receipts.
Withhold or revoke the affected certification and keep submission frozen until a new
venue-observed dossier passes.
