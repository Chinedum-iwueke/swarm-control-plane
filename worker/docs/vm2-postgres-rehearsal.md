# VM2 Postgres Runbook Rehearsal

The production Postgres rollout must remain paused until the disposable
rehearsal completes successfully. Unit tests are necessary but are not the
release gate for this runbook.

## Coverage

The rehearsal executes the compiled broker operations in their production
order:

1. preflight
2. stage
3. private startup
4. schema initialization
5. backup configuration and restore drill
6. deployment verification
7. cutover-readiness assessment

It uses actual Docker Compose containers, bind-mounted configuration,
Postgres UID ownership, generated file secrets, and a transient systemd unit
with the production broker's hardening properties. The PgBouncer host binding
is changed from the VM2 Tailscale address to loopback only for isolation.

## Safety

Run the rehearsal on VM1, never VM2. The script refuses to run when
`/srv/invariance/postgres` already exists. Rehearsal resources are marked and
preserved after the run. Cleanup verifies both the rehearsal marker and
deployment metadata before deleting anything.

The script does not alter the live control plane, create orchestrator tasks,
or use production credentials.

## Execute

```bash
cd /home/omenka/Projects/swarm-control-plane
sudo worker/scripts/rehearse-postgres-runbook.sh run
```

The command runs unattended and prints:

```text
/var/lib/invariance-swarm-rehearsal/report.json
```

A passing report contains all seven phases with `success: true`.

## Inspect

```bash
sudo cat /var/lib/invariance-swarm-rehearsal/report.json

sudo journalctl \
  -u invariance-postgres-rehearsal.service \
  --no-pager \
  --output=cat

sudo docker compose \
  --project-directory /srv/invariance/postgres \
  -f /srv/invariance/postgres/compose.yaml \
  --env-file /srv/invariance/postgres/.env.postgres \
  ps -a
```

## Cleanup

After inspecting the report:

```bash
cd /home/omenka/Projects/swarm-control-plane
sudo worker/scripts/rehearse-postgres-runbook.sh cleanup
```

Do not resume the production mission unless the rehearsal report is green and
the production commit matches the rehearsed commit.
