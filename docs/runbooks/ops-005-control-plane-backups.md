# OPS-005 Control-Plane Backups and Freshness

## Contract

VM2 creates a PostgreSQL custom-format dump every day. A generation becomes visible
only after the dump is non-empty, `pg_restore --list` succeeds, the Alembic marker is
read, and a SHA-256 manifest is atomically published. The non-blocking process lock
rejects overlap. A failed invocation writes `latest-failure.json` but never publishes
its partial dump.

Retention preserves the latest verified generation plus at least 7 daily, 4 weekly,
and 6 monthly buckets. It never deletes the current verified generation. Dumps and
manifests are root-owned, group-readable by `invariance-swarm-backup-readers`, and are
not source-controlled.

The VM2 fleet probe reads only backup metadata and reports age, integrity state, and
whether a newer run failed. Three consecutive observations warn after six days and
become critical after seven days or an explicit failure. Three healthy observations
emit one recovery through the existing founder notification outbox.

## Install

From the VM2 control-plane repository:

```bash
cd /srv/invariance/swarm/repositories/swarm-control-plane/worker
sudo ./systemd/install-control-plane-backup.sh --enable
```

Add this line to `/etc/invariance-swarm/fleet-probe.env` on VM2, reinstall the probe,
and restart it:

```text
SWARM_FLEET_BACKUP_DIRECTORY=/srv/invariance/swarm/control-plane-runtime/backups
```

```bash
sudo ./systemd/install-fleet-probe.sh --enable
sudo systemctl restart invariance-swarm-fleet-probe.service
```

## Operate and verify

```bash
sudo systemctl start invariance-swarm-control-plane-backup.service
sudo systemctl start invariance-swarm-control-plane-backup.service
sudo -u root /opt/invariance-swarm-worker/bin/invariance-swarm-control-plane-backup verify
sudo systemctl start invariance-swarm-control-plane-restore-drill.service
sudo systemctl list-timers --all 'invariance-swarm-control-plane-*'
sudo journalctl -u invariance-swarm-control-plane-backup.service -n 50 --no-pager
sudo journalctl -u invariance-swarm-control-plane-restore-drill.service -n 50 --no-pager
```

The restore drill starts `postgres:17-alpine` with `--network none`, publishes no
ports, restores the latest digest-verified dump, checks the Alembic marker and public
table count, writes `latest-restore-drill.json`, and removes the container. It never
connects to or mutates the production database.

Both hardened units keep `ProtectHome=true` and point Docker at a private empty
`RuntimeDirectory`. Do not redirect Docker to `/root/.docker` or weaken home protection.
They receive the `docker` supplementary group solely to open the mode-`0660` Docker
socket; their Linux capability bounding sets remain empty.

## Failure and recovery

Inspect `latest-failure.json`, journal output, free space, Docker health, and the latest
manifest without printing Compose environment or secrets. Correct the bounded cause,
manually start the backup service once, run `verify`, and wait for three VM2 fleet
samples to close the incident. Do not delete a prior verified generation to make a
failed run appear healthy.

## Rollback

```bash
sudo systemctl disable --now \
  invariance-swarm-control-plane-backup.timer \
  invariance-swarm-control-plane-restore-drill.timer
```

Rollback stops scheduling only. Preserve all dumps, manifests, failure records,
restore dossiers, fleet observations, incidents, and founder notifications.
