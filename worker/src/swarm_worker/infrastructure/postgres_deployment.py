from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POSTGRES_ROOT = Path("/srv/invariance/postgres")
DEPLOYMENT_VERSION = "1.4.0"
_UPGRADABLE_DEPLOYMENT_VERSIONS = {"1.0.0", "1.1.0", "1.2.0", "1.3.0"}
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
        pgbouncer_bind_address: str = "100.112.117.59",
    ) -> None:
        self.root = root
        self.postgres_uid = postgres_uid
        self.postgres_gid = postgres_gid
        self.pgbouncer_bind_address = pgbouncer_bind_address
        self._compose = _COMPOSE.replace(
            "__PGBOUNCER_BIND_ADDRESS__",
            pgbouncer_bind_address,
        )

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
            "cutover",
            "data",
            "init",
            "logs",
            "pgbouncer",
            "schema",
        ):
            path = self.root / name
            runtime_directory = name in {"archive", "data", "logs"}
            path.mkdir(mode=0o750 if runtime_directory else 0o700, exist_ok=True)
            if not runtime_directory:
                path.chmod(0o700)
        for name in ("archive", "data", "logs"):
            if not (self.root / name).is_dir():
                raise PostgresDeploymentError(
                    "Preprovisioned Postgres directory is unavailable."
                )
        self._validate_runtime_directories()
        for name in ("bin", "conf", "init", "schema"):
            (self.root / name).chmod(0o755)

        files = {
            ".env.postgres": self._environment(),
            "compose.yaml": self._compose,
            "compose.client-tls.yaml": _CLIENT_TLS_OVERRIDE,
            "conf/postgresql.conf": _POSTGRESQL_CONF,
            "conf/pg_hba.conf": _PG_HBA,
            "conf/client-allowlist.json": _CLIENT_ALLOWLIST,
            "cutover/application-migration.json": _APPLICATION_MIGRATION_PLAN,
            "cutover/credential-rotation.json": _CREDENTIAL_ROTATION_PLAN,
            "cutover/rollback.json": _ROLLBACK_PLAN,
            "cutover/approval.json": _CUTOVER_APPROVAL,
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
                else 0o600
                if relative == ".env.postgres"
                or relative == "conf/client-allowlist.json"
                or relative.startswith("cutover/")
                else 0o644
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

    def is_staged(self) -> bool:
        metadata_path = self.root / "metadata.json"
        if not metadata_path.is_file():
            return False
        try:
            self._validate_runtime_directories()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (
                metadata.get("deployment") != "vm2-invariance-postgres"
                or metadata.get("deployment_version")
                not in ({DEPLOYMENT_VERSION} | _UPGRADABLE_DEPLOYMENT_VERSIONS)
                or metadata.get("public_access") is not False
                or not isinstance(metadata.get("files"), dict)
            ):
                return False
            for relative, expected in metadata["files"].items():
                path = (self.root / relative).resolve()
                if (
                    not path.is_relative_to(self.root.resolve())
                    or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    return False
        except (OSError, json.JSONDecodeError, PostgresDeploymentError):
            return False
        return True

    def _validate_preprovisioned(self) -> None:
        allowed = {
            "archive",
            "backups",
            "bin",
            "certs",
            "conf",
            "cutover",
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
        self._validate_runtime_directories()
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
        self._validate_runtime_directories()
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PostgresDeploymentError(
                "Non-empty deployment root has no valid metadata."
            ) from exc
        if (
            metadata.get("deployment") != "vm2-invariance-postgres"
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
        deployment_version = metadata.get("deployment_version")
        if deployment_version in _UPGRADABLE_DEPLOYMENT_VERSIONS:
            metadata = self._upgrade_existing(metadata, metadata_path)
        elif deployment_version != DEPLOYMENT_VERSION:
            raise PostgresDeploymentError("Existing deployment metadata mismatches.")
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

    def _upgrade_existing(
        self,
        metadata: dict[str, Any],
        metadata_path: Path,
    ) -> dict[str, Any]:
        self._replace_file(self.root / "compose.yaml", self._compose, 0o644)
        self._replace_file(
            self.root / "compose.client-tls.yaml",
            _CLIENT_TLS_OVERRIDE,
            0o644,
        )
        override_path = self.root / "schema" / "worker-network.override.yaml"
        self._replace_file(override_path, _WORKER_NETWORK_OVERRIDE, 0o644)
        backup_path = self.root / "bin" / "backup.sh"
        self._replace_file(backup_path, _BACKUP_SCRIPT, 0o755)
        hba_path = self.root / "conf" / "pg_hba.conf"
        self._replace_file(hba_path, _PG_HBA, 0o644)
        cutover_files = {
            "conf/client-allowlist.json": _CLIENT_ALLOWLIST,
            "cutover/application-migration.json": _APPLICATION_MIGRATION_PLAN,
            "cutover/credential-rotation.json": _CREDENTIAL_ROTATION_PLAN,
            "cutover/rollback.json": _ROLLBACK_PLAN,
            "cutover/approval.json": _CUTOVER_APPROVAL,
        }
        for relative, content in cutover_files.items():
            path = self.root / relative
            path.parent.mkdir(mode=0o700, exist_ok=True)
            if not path.exists():
                self._write_new(path, content, 0o600)
        metadata["deployment_version"] = DEPLOYMENT_VERSION
        metadata["updated_at"] = datetime.now(UTC).isoformat()
        metadata["files"]["compose.yaml"] = hashlib.sha256(
            self._compose.encode()
        ).hexdigest()
        metadata["files"]["compose.client-tls.yaml"] = hashlib.sha256(
            _CLIENT_TLS_OVERRIDE.encode()
        ).hexdigest()
        metadata["files"]["schema/worker-network.override.yaml"] = hashlib.sha256(
            _WORKER_NETWORK_OVERRIDE.encode()
        ).hexdigest()
        metadata["files"]["bin/backup.sh"] = hashlib.sha256(
            _BACKUP_SCRIPT.encode()
        ).hexdigest()
        metadata["files"]["conf/pg_hba.conf"] = hashlib.sha256(
            _PG_HBA.encode()
        ).hexdigest()
        for relative, content in cutover_files.items():
            metadata["files"][relative] = hashlib.sha256(content.encode()).hexdigest()
        rendered = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        self._replace_file(metadata_path, rendered, 0o600)
        return metadata

    def _validate_runtime_directories(self) -> None:
        for name in ("archive", "data", "logs"):
            path = self.root / name
            if path.is_symlink() or not path.is_dir():
                raise PostgresDeploymentError(
                    "Preprovisioned Postgres directory is unavailable."
                )
            state = path.stat()
            if (
                state.st_uid != self.postgres_uid
                or state.st_gid != self.postgres_gid
                or stat.S_IMODE(state.st_mode) != 0o750
            ):
                raise PostgresDeploymentError(
                    "Preprovisioned Postgres directory ownership is invalid."
                )

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
    def _replace_file(path: Path, content: str, mode: int) -> None:
        temporary = path.with_name(f".{path.name}.worker-new")
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                mode,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

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
    image: postgres:16-bookworm@sha256:92620daddcd947f8d5ab5ba66e848702fe443d87fed30c4cea8e389fd78dfc55
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
    image: edoburu/pgbouncer:v1.24.1-p1@sha256:3db3d7223e93af52b4116f642951a1a5fa44702a88c2a59cf7562cac19320c9e
    container_name: invariance-pgbouncer
    restart: unless-stopped
    depends_on:
      postgres: {condition: service_healthy}
    env_file: [.env.postgres]
    environment:
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: ${INVARIANCE_DB}
      DB_USER: invariance_app
      DB_PASSWORD: ${INVARIANCE_APP_PASSWORD}
      POOL_MODE: transaction
      MAX_CLIENT_CONN: "300"
      DEFAULT_POOL_SIZE: "30"
      MIN_POOL_SIZE: "5"
      RESERVE_POOL_SIZE: "10"
      AUTH_TYPE: scram-sha-256
      IGNORE_STARTUP_PARAMETERS: extra_float_digits
      SERVER_RESET_QUERY: DISCARD ALL
    ports:
    - __PGBOUNCER_BIND_ADDRESS__:6432:5432
    healthcheck:
      test:
      - CMD-SHELL
      - PGPASSWORD=$${INVARIANCE_APP_PASSWORD} psql -h 127.0.0.1 -p 5432
        -U invariance_app -d $${INVARIANCE_DB} -c 'SELECT 1' >/dev/null
      interval: 15s
      timeout: 5s
      retries: 10
    logging:
      driver: json-file
      options: {max-size: 20m, max-file: "5"}
"""

# This overlay is intentionally not included by the private-start operation. It is
# activated only by a separately approved cutover primitive after real certificate,
# DNS, allowlist, migration, credential, and rollback evidence is registered.
_CLIENT_TLS_OVERRIDE = """services:
  pgbouncer:
    environment:
      CLIENT_TLS_SSLMODE: verify-full
      CLIENT_TLS_CA_FILE: /etc/pgbouncer/tls/ca.crt
      CLIENT_TLS_CERT_FILE: /etc/pgbouncer/tls/server.crt
      CLIENT_TLS_KEY_FILE: /etc/pgbouncer/tls/server.key
      CLIENT_TLS_PROTOCOLS: secure
    volumes:
    - ./certs/ca.crt:/etc/pgbouncer/tls/ca.crt:ro
    - ./certs/server.crt:/etc/pgbouncer/tls/server.crt:ro
    - ./certs/server.key:/etc/pgbouncer/tls/server.key:ro
"""

_CLIENT_ALLOWLIST = """{
  "schema_version": 1,
  "default_policy": "deny",
  "clients": []
}
"""

_APPLICATION_MIGRATION_PLAN = """{
  "schema_version": 1,
  "status": "draft",
  "application": "invariance-research-public-web",
  "source_database": null,
  "migration_artifact_sha256": null,
  "data_parity_query_set_sha256": null,
  "maintenance_window": null
}
"""

_CREDENTIAL_ROTATION_PLAN = """{
  "schema_version": 1,
  "status": "draft",
  "distribution": "service-scoped-secret-store",
  "application_role": "invariance_app",
  "previous_credential_retention_minutes": 60,
  "rotation_evidence_sha256": null
}
"""

_ROLLBACK_PLAN = """{
  "schema_version": 1,
  "status": "draft",
  "traffic_restore_target": null,
  "maximum_recovery_time_seconds": 900,
  "rehearsal_evidence_sha256": null,
  "data_reconciliation_artifact_sha256": null
}
"""

_CUTOVER_APPROVAL = """{
  "schema_version": 1,
  "status": "pending",
  "package_manifest_sha256": null,
  "plan_digest": null,
  "approved_by": null,
  "approved_at": null,
  "expires_at": null
}
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
host invariance_research invariance_owner 172.16.0.0/12 scram-sha-256
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
    env_file: !reset []
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
set -a
source "$root/.env.postgres"
set +a
export PGPASSWORD="$POSTGRES_SUPERUSER_PASSWORD"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$root/backups/invariance_research_${stamp}.dump"
cd "$root"
docker compose --env-file "$root/.env.postgres" exec -T -e PGPASSWORD \
  postgres pg_dump \
  -U postgres -d invariance_research -Fc > "$output"
docker compose --env-file "$root/.env.postgres" exec -T postgres \
  pg_restore --list < "$output" >/dev/null
sha256sum "$output" > "$output.sha256"
find "$root/backups" -maxdepth 1 -type f -mtime +14 -delete
"""
