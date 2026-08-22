# OPS-004 Validation Record

**Date:** 2026-08-22
**Status:** Source complete; production activation pending

## Implemented

- Strict low-cardinality observation schema and agent-machine binding.
- Idempotent digest-bound observation storage and explicit raw retention class.
- Sustained CPU, memory, swap, PSI, disk, inode, OOM and service-health evaluation.
- Three-sample breach and recovery hysteresis with incident generations.
- Pending, warning, critical, acknowledged, silenced and recovered incident states.
- Durable incident transition evidence and one founder notification per state change.
- Existing Telegram outbox delivery and Mission Control Fleet Health surface.
- Unprivileged Linux probes for VM1 and VM2.
- Independent bounded TCP watchdog for simultaneous outage detection.
- Prometheus sample-age and incident-state metrics.

## Verified locally

- A transient breach emits no notification.
- A sustained breach emits exactly one notification.
- Sustained recovery emits exactly one recovery notification.
- Watchdog outage and recovery messages deduplicate across repeated cycles.
- Probe service checks use subprocess argument arrays and a controlled environment.
- Agent token is carried only in the Authorization header, not the observation body.
- Unknown schema fields and duplicate service names fail closed.

## Production acceptance gate

OPS-004 must not be marked `deployed`, `active`, or production-qualified until migration
`b6f2a9c41d80` is applied, both host probes publish live samples, Telegram transition
delivery is observed, and an always-on third observer completes the simultaneous-outage
rehearsal. No automatic remediation is part of OPS-004.
