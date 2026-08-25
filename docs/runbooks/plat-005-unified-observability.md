# PLAT-005 unified observability, SLO and alert routing

## Operating model

PLAT-005 consumes the active PLAT-001 service catalog, authenticated OPS-004 fleet
samples, OPS-005 backup freshness, the latest catalog reconciliation and OPS-007
operation progress. It does not introduce a second machine probe, incident channel or
notification outbox.

Each fleet sample triggers a bounded evaluation. Service SLO state is keyed by stable
catalog `service_key` and indicator. Availability is explicitly current-window evidence;
a single health sample is never presented as historical uptime. Recovery objectives
without a measured restore remain `unknown`, not healthy.

Three consecutive missing or breached evaluations open one alert generation. Three
healthy evaluations recover it. Recurrence after recovery increments the generation.
Acknowledgement and time-bounded silence append routing events and never change the
underlying SLO measurement. Telegram delivery uses the existing durable founder outbox.

## Deployment

On VM2 after the merged source is pulled:

```bash
cd /srv/invariance/swarm/control-plane-runtime
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
docker compose up -d --no-deps --force-recreate api
```

Reinstall Mission Control on the Mac and the Telegram gateway on VM2 using their
existing installers because both clients gained the new observability contract.

## Verification

1. `GET /v1/observability/overview` returns the active catalog digest, status counts,
   attributed service indicators and active alerts.
2. Trigger three synthetic or rehearsed breaches; exactly one founder notification is
   delivered for the generation.
3. Acknowledge or silence in Mission Control and verify an immutable routing event.
4. Restore health for three evaluations and verify one recovery notification.
5. Confirm `/v1/metrics` exports `hermes_service_slo_state` and
   `hermes_routed_service_alerts` with bounded labels.

## Rollback

Disable evaluation by restoring the prior API image. The migration is additive and its
tables may remain for audit. Revert a noisy rule in source rather than deleting alert
history. Existing fleet probes, incidents, operations and founder notifications remain
independent and available.

## Claim boundary

PLAT-005 provides service-attributed current SLO evidence and accountable routing. It
does not claim long-window availability until sufficient samples are retained, does not
replace external correlated-outage detection, and grants no automated remediation or
capital authority.
