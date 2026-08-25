# SEC-001 system security assurance

## Purpose

SEC-001 keeps a versioned system threat model aligned with the canonical PLAT-001
service catalog and proves five mandatory hostile paths fail closed: instruction
injection, secret exfiltration, privilege escalation, supply-chain tampering, and
capital-authority mutation.

The suite is defensive and non-production-mutating. It uses synthetic hostile
fixtures, never live credentials or live capital authority.

## Run

```bash
cd /home/omenka/Projects/swarm-control-plane
worker/.venv/bin/python worker/scripts/sec001_adversarial_suite.py \
  --model worker/security/hermes-system-threat-model-v1.json \
  --catalog worker/service-catalog/hermes-platform-v1.json \
  --output docs/evidence/sec001-report.json
```

The command fails if any catalog service lacks threat coverage, the model review is
overdue, a threat lacks detection/containment/rollback ownership, a reference is
invalid, or a hostile fixture does not produce its declared fail-closed outcome.

## Change control

Any new catalog service must be assigned at least one abuse case before CI passes.
Every high-risk interface must retain controls, detection, containment, rollback,
an owner, residual risk, and adversarial verification. Review the model at least
every six months and after a trust-boundary, capital-authority, credential, or
external integration change.

## Incident containment

Use the threat-specific rollback in the model. Do not suppress scanner findings or
edit a report to turn a failed scenario into a pass. Revoke affected credentials or
deployments, disable the unsafe surface, preserve redacted evidence, repair the
underlying control, and rerun the complete suite.

## Residual risks

SEC-001 deliberately reports accepted gaps. Current material gaps include uniform
workflow egress allowlisting, complete signed provenance for third-party dependency
artifacts, independent dual-VM outage alerting, and host-root compromise. A green
report means the declared controls passed; it does not claim these risks disappeared.
