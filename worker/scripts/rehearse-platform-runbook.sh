#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this rehearsal as root on VM2.\n' >&2
  exit 1
fi

action=${1:-run}
repo=/srv/invariance/swarm/repositories/swarm-control-plane
worker="$repo/worker"
root=/srv/invariance/platform-rehearsal
state=/var/lib/invariance-swarm-platform-rehearsal
unit=invariance-platform-runbook-rehearsal
timer=hermes-platform-rehearsal-backup.timer
service=hermes-platform-rehearsal-backup.service
marker=vm2-platform-operations

guard_rehearsal() {
  test -f "$state/DISPOSABLE_REHEARSAL"
  test "$(cat "$state/DISPOSABLE_REHEARSAL")" = "$marker"
  test -f "$root/DISPOSABLE_REHEARSAL"
  test "$(cat "$root/DISPOSABLE_REHEARSAL")" = "$marker"
}

cleanup() {
  guard_rehearsal
  systemctl disable --now "$timer" 2>/dev/null || true
  docker compose \
    --project-directory "$root" \
    -f "$root/compose.yaml" \
    --env-file "$root/.env.postgres" \
    down --volumes --remove-orphans 2>/dev/null || true
  rm -f "/etc/systemd/system/$timer" "/etc/systemd/system/$service"
  systemctl daemon-reload
  rm -rf "$root"
}

if [[ $action == cleanup ]]; then
  cleanup
  printf 'Disposable VM2 platform rehearsal removed.\n'
  exit 0
fi
if [[ $action != run ]]; then
  printf 'Usage: %s [run|cleanup]\n' "$0" >&2
  exit 2
fi
test -d "$repo/.git"
test -x "$worker/.venv/bin/python"
test -S /var/run/docker.sock

if [[ -e $root ]]; then
  if [[ -f $state/DISPOSABLE_REHEARSAL ]]; then
    printf 'Recovering the previous marked platform rehearsal.\n'
    cleanup
  else
    printf '%s exists without a matching rehearsal marker; refusing.\n' "$root" >&2
    exit 1
  fi
fi

install -d -o root -g root -m 0700 "$root" "$root/backups" "$root/certs" "$state"
printf '%s\n' "$marker" > "$root/DISPOSABLE_REHEARSAL"
printf '%s\n' "$marker" > "$state/DISPOSABLE_REHEARSAL"
chmod 0600 "$root/DISPOSABLE_REHEARSAL" "$state/DISPOSABLE_REHEARSAL"
rm -f "$state/consumed.json" "$state/report.json"

cat > "$root/.env.postgres" <<'EOF'
POSTGRES_PASSWORD=platform-rehearsal-only
EOF
chmod 0600 "$root/.env.postgres"

cat > "$root/compose.yaml" <<'EOF'
name: hermes-platform-rehearsal
services:
  api:
    image: redis:7-alpine
    container_name: hermes-platform-rehearsal-api
    command: ["redis-server", "--save", ""]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 2s
      timeout: 2s
      retries: 20
  postgres:
    image: postgres:16-bookworm
    container_name: hermes-platform-rehearsal-postgres
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 2s
      timeout: 2s
      retries: 30
  pgbouncer:
    image: redis:7-alpine
    container_name: hermes-platform-rehearsal-pgbouncer
    command: ["redis-server", "--save", ""]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 2s
      timeout: 2s
      retries: 20
  redis:
    image: redis:7-alpine
    container_name: hermes-platform-rehearsal-redis
    command: ["redis-server", "--save", ""]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 2s
      timeout: 2s
      retries: 20
EOF
chmod 0600 "$root/compose.yaml"

openssl req -x509 -newkey rsa:2048 -nodes -days 60 \
  -subj '/CN=db-rehearsal.invarianceresearch.internal' \
  -addext 'subjectAltName=DNS:db-rehearsal.invarianceresearch.internal' \
  -keyout "$root/certs/server.key" \
  -out "$root/certs/server.crt" >/dev/null 2>&1
chmod 0600 "$root/certs/server.key" "$root/certs/server.crt"

cat > "/etc/systemd/system/$service" <<'EOF'
[Unit]
Description=Disposable Hermes platform rehearsal backup marker
[Service]
Type=oneshot
ExecStart=/usr/bin/true
EOF
cat > "/etc/systemd/system/$timer" <<EOF
[Unit]
Description=Disposable Hermes platform rehearsal backup timer
[Timer]
OnCalendar=daily
Unit=$service
[Install]
WantedBy=timers.target
EOF
chmod 0644 "/etc/systemd/system/$service" "/etc/systemd/system/$timer"
systemctl daemon-reload
systemctl enable "$timer" >/dev/null

docker compose \
  --project-directory "$root" \
  -f "$root/compose.yaml" \
  --env-file "$root/.env.postgres" \
  up -d --wait

docker exec \
  -e PGPASSWORD=platform-rehearsal-only \
  hermes-platform-rehearsal-postgres \
  pg_dump -U postgres -Fc postgres > "$root/backups/platform-rehearsal.dump"
chmod 0600 "$root/backups/platform-rehearsal.dump"

set +e
systemd-run \
  --unit="$unit" \
  --wait \
  --pipe \
  --collect \
  --property=Type=oneshot \
  --property=User=root \
  --property=NoNewPrivileges=yes \
  --property=PrivateTmp=yes \
  --property=ProtectSystem=strict \
  --property=ProtectHome=yes \
  --property=ProtectKernelTunables=yes \
  --property=ProtectKernelModules=yes \
  --property=ProtectKernelLogs=yes \
  --property=ProtectControlGroups=yes \
  --property=ProtectClock=yes \
  --property=ProtectHostname=yes \
  --property=RestrictRealtime=yes \
  --property=RestrictSUIDSGID=yes \
  --property=LockPersonality=yes \
  --property=MemoryDenyWriteExecute=yes \
  --property=CapabilityBoundingSet= \
  --property='RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6' \
  --property="ReadOnlyPaths=$repo" \
  --property="ReadOnlyPaths=$root" \
  --property="ReadWritePaths=$state" \
  "$worker/.venv/bin/python" \
  "$worker/scripts/rehearse_platform_runbook.py" \
  --root "$root" \
  --state "$state" \
  --source "$repo"
status=$?
set -e

cat "$state/report.json"
printf 'Rehearsal resources and evidence were preserved for inspection.\n'
printf 'Cleanup: sudo %s cleanup\n' "$0"
exit "$status"
