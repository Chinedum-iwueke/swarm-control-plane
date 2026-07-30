from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POSTGRES_ROOT = Path("/srv/invariance/postgres")
DEPLOYMENT_VERSION = "1.0.0"
UTC = timezone.utc


class PostgresDeploymentError(Exception):
    """The reviewed Postgres deployment cannot proceed safely."""


class PostgresDeploymentManager:
    def __init__(
        self,
        root: Path = POSTGRES_ROOT,
        *,
        postgres_uid: int = 999,
        postgres_gid: int = 999,
    ) -> None:
        self.root = root
        self.postgres_uid = postgres_uid
        self.postgres_gid = postgres_gid

    def stage(self) -> dict[str, Any]:
        metadata_path = self.root / "metadata.json"
        if self.root.exists() and any(self.root.iterdir()):
            if metadata_path.exists():
                return self._validate_existing(metadata_path)
            self._validate_preprovisioned()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        for name in (
            "archive",
            "backups",
            "bin",
            "certs",
            "conf",
            "data",
            "init",
            "logs",
            "pgbouncer",
            "schema",
        ):
            path = self.root / name
            path.mkdir(mode=0o700, exist_ok=True)
            path.chmod(0o700)
        for name in ("archive", "data", "logs"):
            stat = (self.root / name).stat()
            if (
                stat.st_uid != self.postgres_uid
                or stat.st_gid != self.postgres_gid
            ):
                raise PostgresDeploymentError(
                    "Preprovisioned Postgres directory ownership is invalid."
                )
        for name in ("bin", "conf", "init", "schema"):
            (self.root / name).chmod(0o755)

        files = {
            ".env.postgres": self._environment(),
            "compose.yaml": _COMPOSE,
            "conf/postgresql.conf": _POSTGRESQL_CONF,
            "conf/pg_hba.conf": _PG_HBA,
            "init/001-invariance.sh": _INIT_SCRIPT,
            "schema/001-broker-marker.sql": _SCHEMA_MARKER,
            "schema/worker-network.override.yaml": _WORKER_NETWORK_OVERRIDE,
            "bin/backup.sh": _BACKUP_SCRIPT,
        }
        digests: dict[str, str] = {}
        for relative, content in files.items():
            mode = (
                0o755
                if relative.endswith(".sh")
                else 0o644
                if relative != ".env.postgres"
                else 0o600
            )
            path = self.root / relative
            self._write_new(path, content, mode)
            digests[relative] = hashlib.sha256(content.encode()).hexdigest()

        metadata = {
            "schema_version": 1,
            "deployment": "vm2-invariance-postgres",
            "deployment_version": DEPLOYMENT_VERSION,
            "network_mode": "tailscale-private",
            "public_access": False,
            "created_at": datetime.now(UTC).isoformat(),
            "files": digests,
        }
        rendered = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        self._write_new(metadata_path, rendered, 0o600)
        return {
            "staged": True,
            "reused": False,
            "root": str(self.root),
            "network_mode": "tailscale-private",
            "public_access": False,
            "metadata_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
            "file_digests": digests,
        }

    def is_preprovisioned(self) -> bool:
        if not self.root.is_dir():
            return False
        try:
            self._validate_preprovisioned()
        except PostgresDeploymentError:
            return False
        return True

    def _validate_preprovisioned(self) -> None:
        allowed = {
            "archive",
            "backups",
            "bin",
            "certs",
            "conf",
            "data",
            "init",
            "logs",
            "pgbouncer",
            "schema",
        }
        entries = {path.name: path for path in self.root.iterdir()}
        if set(entries) != allowed:
            raise PostgresDeploymentError(
                "Non-empty deployment root has no valid metadata."
            )
        if any(
            path.is_symlink()
            or not path.is_dir()
            or any(path.iterdir())
            for path in entries.values()
        ):
            raise PostgresDeploymentError(
                "Preprovisioned deployment layout is not empty."
            )

    def _validate_existing(self, metadata_path: Path) -> dict[str, Any]:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PostgresDeploymentError(
                "Non-empty deployment root has no valid metadata."
            ) from exc
        if (
            metadata.get("deployment") != "vm2-invariance-postgres"
            or metadata.get("deployment_version") != DEPLOYMENT_VERSION
            or metadata.get("public_access") is not False
            or not isinstance(metadata.get("files"), dict)
        ):
            raise PostgresDeploymentError("Existing deployment metadata mismatches.")
        for relative, expected in metadata["files"].items():
            path = (self.root / relative).resolve()
            if not path.is_relative_to(self.root.resolve()) or not path.is_file():
                raise PostgresDeploymentError("Staged deployment file is unavailable.")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise PostgresDeploymentError("Staged deployment digest mismatches.")
        rendered = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        return {
            "staged": True,
            "reused": True,
            "root": str(self.root),
            "network_mode": metadata["network_mode"],
            "public_access": False,
            "metadata_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
            "file_digests": metadata["files"],
        }

    @staticmethod
    def _write_new(path: Path, content: str, mode: int) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(mode)

    @staticmethod
    def _environment() -> str:
        values = {
            "POSTGRES_SUPERUSER_PASSWORD": secrets.token_urlsafe(48),
            "INVARIANCE_OWNER_PASSWORD": secrets.token_urlsafe(48),
            "INVARIANCE_APP_PASSWORD": secrets.token_urlsafe(48),
            "INVARIANCE_WORKER_PASSWORD": secrets.token_urlsafe(48),
            "PGBOUNCER_ADMIN_PASSWORD": secrets.token_urlsafe(48),
        }
        return "INVARIANCE_DB=invariance_research\n" + "".join(
            f"{name}={value}\n" for name, value in values.items()
        )


_COMPOSE = """name: invariance-postgres
services:
  postgres:
    image: postgres:16-bookworm
    container_name: invariance-postgres
    restart: unless-stopped
    env_file: [.env.postgres]
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_SUPERUSER_PASSWORD}
      POSTGRES_DB: ${INVARIANCE_DB}
      PGDATA: /var/lib/postgresql/data/pgdata
    command:
    - postgres
    - -c
    - config_file=/etc/postgresql/postgresql.conf
    - -c
    - hba_file=/etc/postgresql/pg_hba.conf
    ports:
    - 127.0.0.1:5432:5432
    volumes:
    - ./data:/var/lib/postgresql/data
    - ./conf/postgresql.conf:/etc/postgresql/postgresql.conf:ro
    - ./conf/pg_hba.conf:/etc/postgresql/pg_hba.conf:ro
    - ./init:/docker-entrypoint-initdb.d:ro
    - ./archive:/var/lib/postgresql/archive
    - ./logs:/var/log/postgresql
    healthcheck:
      test:
      - CMD-SHELL
      - 'pg_isready -U postgres -d "$${INVARIANCE_DB}"'
      interval: 15s
      timeout: 5s
      retries: 10
    logging:
      driver: json-file
      options: {max-size: 50m, max-file: "5"}
  pgbouncer:
    image: bitnami/pgbouncer:1.24.1
    container_name: invariance-pgbouncer
    restart: unless-stopped
    depends_on:
      postgres: {condition: service_healthy}
    env_file: [.env.postgres]
    environment:
      POSTGRESQL_HOST: postgres
      POSTGRESQL_PORT: "5432"
      POSTGRESQL_DATABASE: ${INVARIANCE_DB}
      POSTGRESQL_USERNAME: invariance_app
      POSTGRESQL_PASSWORD: ${INVARIANCE_APP_PASSWORD}
      PGBOUNCER_DATABASE: ${INVARIANCE_DB}
      PGBOUNCER_PORT: "6432"
      PGBOUNCER_POOL_MODE: transaction
      PGBOUNCER_MAX_CLIENT_CONN: "300"
      PGBOUNCER_DEFAULT_POOL_SIZE: "30"
      PGBOUNCER_MIN_POOL_SIZE: "5"
      PGBOUNCER_RESERVE_POOL_SIZE: "10"
      PGBOUNCER_AUTH_TYPE: scram-sha-256
      PGBOUNCER_IGNORE_STARTUP_PARAMETERS: extra_float_digits
      PGBOUNCER_SERVER_RESET_QUERY: DISCARD ALL
      PGBOUNCER_ADMIN_USERS: postgres
      PGBOUNCER_STATS_USERS: postgres
    ports:
    - 100.112.117.59:6432:6432
    healthcheck:
      test:
      - CMD-SHELL
      - PGPASSWORD=$${INVARIANCE_APP_PASSWORD} psql -h 127.0.0.1 -p 6432
        -U invariance_app -d $${INVARIANCE_DB} -c 'SELECT 1' >/dev/null
      interval: 15s
      timeout: 5s
      retries: 10
    logging:
      driver: json-file
      options: {max-size: 20m, max-file: "5"}
"""

_POSTGRESQL_CONF = """listen_addresses = '*'
port = 5432
password_encryption = scram-sha-256
ssl = off
max_connections = 100
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 16MB
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB
idle_in_transaction_session_timeout = 30000
statement_timeout = 120000
lock_timeout = 10000
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_min_duration_statement = 500
log_line_prefix = '%m [%p] %u@%d %r '
log_connections = on
log_disconnections = on
log_lock_waits = on
timezone = 'UTC'
"""

_PG_HBA = """local all all scram-sha-256
host all all 127.0.0.1/32 scram-sha-256
host all all ::1/128 scram-sha-256
host invariance_research invariance_app 172.16.0.0/12 scram-sha-256
host invariance_research invariance_worker 172.16.0.0/12 scram-sha-256
"""

_INIT_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=owner_password="$INVARIANCE_OWNER_PASSWORD" \
  --set=app_password="$INVARIANCE_APP_PASSWORD" \
  --set=worker_password="$INVARIANCE_WORKER_PASSWORD" <<'SQL'
CREATE ROLE invariance_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE invariance_app LOGIN PASSWORD :'app_password';
CREATE ROLE invariance_worker LOGIN PASSWORD :'worker_password';
ALTER DATABASE invariance_research OWNER TO invariance_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO invariance_owner;
GRANT CONNECT ON DATABASE invariance_research TO invariance_app;
GRANT CONNECT ON DATABASE invariance_research TO invariance_worker;
GRANT USAGE ON SCHEMA public TO invariance_app;
GRANT USAGE ON SCHEMA public TO invariance_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE invariance_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO invariance_app;
ALTER DEFAULT PRIVILEGES FOR ROLE invariance_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO invariance_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE invariance_owner IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO invariance_app;
ALTER DEFAULT PRIVILEGES FOR ROLE invariance_owner IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO invariance_worker;
SQL
"""

_SCHEMA_MARKER = """BEGIN;
CREATE TABLE IF NOT EXISTS hermes_schema_operations (
  operation text PRIMARY KEY,
  source_commit text NOT NULL,
  applied_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO hermes_schema_operations (operation, source_commit)
VALUES ('invariance-schema-initialized', current_setting('application_name'))
ON CONFLICT (operation) DO NOTHING;
COMMIT;
"""

_WORKER_NETWORK_OVERRIDE = """services:
  analysis-worker:
    networks:
    - invariance-postgres
networks:
  invariance-postgres:
    external: true
    name: invariance-postgres_default
"""

_BACKUP_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail
umask 077
root=/srv/invariance/postgres
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$root/backups/invariance_research_${stamp}.dump"
cd "$root"
docker compose exec -T postgres pg_dump \
  -U postgres -d invariance_research -Fc > "$output"
docker compose exec -T postgres pg_restore --list < "$output" >/dev/null
sha256sum "$output" > "$output.sha256"
find "$root/backups" -maxdepth 1 -type f -mtime +14 -delete
"""
