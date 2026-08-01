#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

mode="${1:-activate}"
if [[ "$mode" != activate && "$mode" != validate ]]; then
  echo "Usage: $0 [validate|activate]" >&2
  exit 2
fi

root=/srv/invariance/postgres
compose="$root/compose.yaml"
overlay="$root/compose.app-tls.yaml"
env_file="$root/.env.postgres"
backup="$root/cutover/pre-app-tls-$(date -u +%Y%m%dT%H%M%SZ)"
image='edoburu/pgbouncer:v1.25.2-p0@sha256:7d7a27d9e90985cab5cf42256f5c13a3120baa4b055b69df37beb272b89b2340'

for path in \
  "$compose" \
  "$env_file" \
  "$root/conf/postgresql.conf" \
  "$root/conf/pg_hba.conf" \
  "$root/certs/ca.crt" \
  "$root/certs/server.crt" \
  "$root/certs/server.key" \
  "$root/certs/pgbouncer-app.crt" \
  "$root/certs/pgbouncer-app.key"; do
  test -f "$path"
done

test "$(docker network inspect invariance-data-private --format '{{.Internal}}')" = true
openssl verify -CAfile "$root/certs/ca.crt" "$root/certs/server.crt"
openssl verify -CAfile "$root/certs/ca.crt" "$root/certs/pgbouncer-app.crt"
openssl x509 -in "$root/certs/server.crt" -noout -checkhost postgres
openssl x509 -in "$root/certs/pgbouncer-app.crt" -noout -checkhost pgbouncer-app

install -d -o root -g root -m 0700 "$backup"
install -o root -g root -m 0644 "$compose" "$backup/compose.yaml"
if [[ -f "$overlay" ]]; then
  install -o root -g root -m 0600 "$overlay" "$backup/compose.app-tls.yaml"
fi

umask 077
temporary="$(mktemp "$root/.compose.app-tls.XXXXXX")"
cleanup() {
  rm -f "$temporary"
}
trap cleanup EXIT

cat >"$temporary" <<EOF
services:
  postgres:
    command:
      - postgres
      - -c
      - config_file=/etc/postgresql/postgresql.conf
      - -c
      - hba_file=/etc/postgresql/pg_hba.conf
      - -c
      - ssl=on
      - -c
      - ssl_ca_file=/etc/postgresql/tls/ca.crt
      - -c
      - ssl_cert_file=/etc/postgresql/tls/server.crt
      - -c
      - ssl_key_file=/etc/postgresql/tls/server.key
    volumes:
      - ./certs/ca.crt:/etc/postgresql/tls/ca.crt:ro
      - ./certs/server.crt:/etc/postgresql/tls/server.crt:ro
      - ./certs/server.key:/etc/postgresql/tls/server.key:ro
    networks:
      - default
      - data-private

  pgbouncer-app:
    image: $image
    container_name: invariance-pgbouncer-app
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    env_file:
      - .env.postgres
    environment:
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: \${INVARIANCE_DB}
      DB_USER: invariance_app
      DB_PASSWORD: \${INVARIANCE_APP_PASSWORD}
      LISTEN_PORT: "6432"
      POOL_MODE: transaction
      MAX_CLIENT_CONN: "200"
      DEFAULT_POOL_SIZE: "20"
      MIN_POOL_SIZE: "3"
      RESERVE_POOL_SIZE: "5"
      AUTH_TYPE: scram-sha-256
      IGNORE_STARTUP_PARAMETERS: extra_float_digits
      SERVER_RESET_QUERY: DISCARD ALL
      CLIENT_TLS_SSLMODE: require
      CLIENT_TLS_CA_FILE: /etc/pgbouncer/tls/ca.crt
      CLIENT_TLS_CERT_FILE: /etc/pgbouncer/tls/pgbouncer-app.crt
      CLIENT_TLS_KEY_FILE: /etc/pgbouncer/tls/pgbouncer-app.key
      CLIENT_TLS_PROTOCOLS: secure
      SERVER_TLS_SSLMODE: verify-full
      SERVER_TLS_CA_FILE: /etc/pgbouncer/tls/ca.crt
      SERVER_TLS_PROTOCOLS: secure
    volumes:
      - ./certs/ca.crt:/etc/pgbouncer/tls/ca.crt:ro
      - ./certs/pgbouncer-app.crt:/etc/pgbouncer/tls/pgbouncer-app.crt:ro
      - ./certs/pgbouncer-app.key:/etc/pgbouncer/tls/pgbouncer-app.key:ro
    networks:
      - data-private
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          PGPASSWORD=\$\${INVARIANCE_APP_PASSWORD}
          PGSSLMODE=verify-full
          PGSSLROOTCERT=/etc/pgbouncer/tls/ca.crt
          psql -h pgbouncer-app -p 6432 -U invariance_app
          -d \$\${INVARIANCE_DB} -c 'SELECT 1' >/dev/null
      interval: 15s
      timeout: 5s
      retries: 10
    logging:
      driver: json-file
      options:
        max-size: 20m
        max-file: "5"

networks:
  data-private:
    external: true
    name: invariance-data-private
EOF

chmod 0644 "$temporary"
docker compose \
  --project-directory "$root" \
  -f "$compose" \
  -f "$temporary" \
  --env-file "$env_file" \
  config --quiet
mv "$temporary" "$overlay"
chmod 0644 "$overlay"

if [[ "$mode" == validate ]]; then
  echo "Application database TLS overlay validated successfully."
  exit 0
fi

compose_command=(
  docker compose
  --project-directory "$root"
  -f "$compose"
  -f "$overlay"
  --env-file "$env_file"
)

rollback_on_error() {
  status=$?
  trap - ERR
  echo "TLS activation failed; restoring the previous database route." >&2
  docker rm -f invariance-pgbouncer-app >/dev/null 2>&1 || true
  docker compose \
    --project-directory "$root" \
    -f "$compose" \
    --env-file "$env_file" \
    up -d --no-deps --force-recreate postgres || true
  exit "$status"
}
trap rollback_on_error ERR

"${compose_command[@]}" up -d --no-deps --force-recreate postgres

for _ in $(seq 1 30); do
  [[ "$(docker inspect invariance-postgres --format '{{.State.Health.Status}}')" == healthy ]] && break
  sleep 2
done
test "$(docker inspect invariance-postgres --format '{{.State.Health.Status}}')" = healthy

"${compose_command[@]}" up -d --no-deps pgbouncer-app
for _ in $(seq 1 30); do
  [[ "$(docker inspect invariance-pgbouncer-app --format '{{.State.Health.Status}}')" == healthy ]] && break
  sleep 2
done
test "$(docker inspect invariance-pgbouncer-app --format '{{.State.Health.Status}}')" = healthy

test "$(docker exec invariance-pgbouncer-app sh -ec \
  'PGPASSWORD="$INVARIANCE_APP_PASSWORD" PGSSLMODE=verify-full \
  PGSSLROOTCERT=/etc/pgbouncer/tls/ca.crt \
  psql -h postgres -p 5432 -U invariance_app -d "$INVARIANCE_DB" \
  -Atc "select ssl from pg_stat_ssl where pid = pg_backend_pid()"')" = t

docker exec invariance-pgbouncer sh -ec \
  'PGPASSWORD="$INVARIANCE_APP_PASSWORD" psql -h 127.0.0.1 -p 5432 -U invariance_app -d "$INVARIANCE_DB" -Atc "select 1"' \
  | grep -qx 1

docker inspect invariance-pgbouncer-app --format '{{range .NetworkSettings.Networks}}{{println .NetworkID}}{{end}}' >/dev/null

trap - ERR
echo "Application database TLS route activated successfully."
echo "Rollback snapshot: $backup"
