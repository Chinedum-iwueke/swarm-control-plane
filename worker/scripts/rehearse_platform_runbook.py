#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from swarm_worker.infrastructure.broker import (
    BrokerError,
    FixedRunner,
    InfrastructureBroker,
)
from swarm_worker.infrastructure.packages import load_runbook_package
from swarm_worker.models import BrokerTicketPayload, BrokerTicketResponse

UTC = timezone.utc
SECRET = "vm2-platform-rehearsal-ticket-secret-2026"
TASK_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
AGENT_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


class RollbackFaultRunner(FixedRunner):
    """Inject one unhealthy post-restart observation, then run the real rollback."""

    def __init__(self, target_container: str) -> None:
        self._target_container = target_container
        self._fault_enabled = False
        self._fault_armed = False
        self.fault_observed = False

    def enable_fault(self) -> None:
        self._fault_enabled = True

    def run(self, args: Any, **kwargs: Any) -> dict[str, Any]:
        command = tuple(args)
        result = super().run(command, **kwargs)
        if (
            self._fault_enabled
            and "restart" in command
            and result["return_code"] == 0
        ):
            self._fault_armed = True
        elif (
            self._fault_armed
            and command[:6]
            == ("docker", "compose", "up", "-d", "--no-deps", "--force-recreate")
        ):
            self._fault_armed = False
        elif (
            self._fault_armed
            and command[:3] == ("docker", "inspect", self._target_container)
        ):
            self.fault_observed = True
            return {
                "args": list(command),
                "return_code": 0,
                "stdout": "running unhealthy\n",
                "stderr": "",
            }
        return result


def _ticket(
    *,
    package_digest: str,
    operation: str,
    task_type: str,
    risk: int,
    parameters: dict[str, Any],
    attempt: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    payload = BrokerTicketPayload(
        schema_version=1,
        task_id=TASK_ID,
        task_number=f"PLATFORM-REHEARSAL-{attempt:02d}",
        attempt_number=attempt,
        agent_id=AGENT_ID,
        machine="vm2-deployment",
        task_type=task_type,
        risk_level=risk,
        plan_digest=hashlib.sha256(
            f"{operation}:{attempt}".encode()
        ).hexdigest(),
        contract={
            "runbook": "vm2-platform-operations",
            "runbook_version": "1.0.0",
            "operation": operation,
            "target": "vm2-production",
            "parameters": parameters,
            "package_name": "vm2-platform-operations",
            "package_version": "1.0.0",
            "package_digest": package_digest,
        },
        nonce=hashlib.sha256(f"{operation}:{attempt}:nonce".encode()).hexdigest(),
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return BrokerTicketResponse(
        payload=payload,
        signature=hmac.new(SECRET.encode(), canonical, hashlib.sha256).hexdigest(),
    ).model_dump(mode="json")


def _digest(document: object) -> str:
    encoded = json.dumps(
        document,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _source_commit(source: Path) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={source}",
            "-C",
            str(source),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    commit = completed.stdout.strip()
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise RuntimeError("source commit is unavailable")
    return commit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/srv/invariance/platform-rehearsal"),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("/var/lib/invariance-swarm-platform-rehearsal"),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/srv/invariance/swarm/repositories/swarm-control-plane"),
    )
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("the VM2 platform rehearsal must run as root")
    marker = args.state / "DISPOSABLE_REHEARSAL"
    if marker.read_text(encoding="utf-8").strip() != "vm2-platform-operations":
        parser.error("disposable rehearsal marker is unavailable")

    packages = args.source / "worker" / "runbook-packages"
    package_path = packages / "vm2-platform-operations.yaml"
    package = load_runbook_package(packages, "vm2-platform-operations")
    source_commit = _source_commit(args.source)

    services = {
        name: (name, args.root, f"hermes-platform-rehearsal-{name}")
        for name in ("api", "postgres", "pgbouncer", "redis")
    }
    runner = RollbackFaultRunner(services["api"][2])
    broker = InfrastructureBroker(
        secret=SECRET,
        ledger_path=args.state / "consumed.json",
        runner=runner,
        effective_uid=0,
        runtime_path=args.root,
        backup_path=args.root / "backups",
        postgres_root=args.root,
        runbook_packages_path=packages,
        platform_services=services,
        backup_timer_unit="hermes-platform-rehearsal-backup.timer",
        platform_health_attempts=10,
        platform_health_interval_seconds=0.5,
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "environment": {
            "target_profile": package.manifest.rehearsal.target_profile,
            "machine": platform.node(),
            "kernel": platform.release(),
            "python": platform.python_version(),
            "effective_uid": os.geteuid(),
            "docker": runner.run(["docker", "version", "--format", "{{.Server.Version}}"]),
            "docker_compose": runner.run(["docker", "compose", "version", "--short"]),
            "sandbox": {
                "no_new_privileges": True,
                "protect_system": "strict",
                "protect_home": True,
                "capability_bounding_set": "empty",
                "address_families": ["AF_UNIX", "AF_INET", "AF_INET6"],
            },
        },
        "source": {
            "repository": "swarm-control-plane",
            "commit": source_commit,
        },
        "package": {
            "name": package.manifest.name,
            "version": package.manifest.version,
            "manifest_digest": package.manifest_digest,
            "artifact_sha256": hashlib.sha256(package_path.read_bytes()).hexdigest(),
            "rehearsal_required_evidence": package.manifest.rehearsal.required_evidence,
        },
        "production_resources_touched": False,
        "phases": [],
        "success": False,
    }
    report_path = args.state / "report.json"

    operations = [
        *(('verify-docker-service', {"service": name}) for name in services),
        ("verify-service-health", {"service": "api"}),
        ("verify-redis", {}),
        ("verify-storage", {}),
        ("verify-certificate", {"certificate_profile": "invariance-postgres-client"}),
        ("verify-backup", {}),
        ("restart-docker-service", {"service": "api"}),
    ]
    try:
        for attempt, (operation, parameters) in enumerate(operations, 1):
            definition = next(
                item for item in package.manifest.operations if item.name == operation
            )
            result = broker.execute(
                _ticket(
                    package_digest=package.manifest_digest,
                    operation=operation,
                    task_type=definition.task_type,
                    risk=definition.risk_level,
                    parameters=parameters,
                    attempt=attempt,
                )
            )
            document = result.model_dump(mode="json")
            report["phases"].append(
                {
                    "operation": operation,
                    "parameters": parameters,
                    "success": result.success,
                    "result_sha256": _digest(document),
                    "result": document,
                }
            )
            if not result.success:
                raise RuntimeError(f"{operation} failed")

        runner.enable_fault()
        attempt = len(operations) + 1
        definition = next(
            item
            for item in package.manifest.operations
            if item.name == "restart-docker-service"
        )
        rollback_result = broker.execute(
            _ticket(
                package_digest=package.manifest_digest,
                operation="restart-docker-service",
                task_type=definition.task_type,
                risk=definition.risk_level,
                parameters={"service": "api"},
                attempt=attempt,
            )
        )
        rollback_document = rollback_result.model_dump(mode="json")
        rollback_passed = bool(
            runner.fault_observed
            and not rollback_result.success
            and rollback_result.rollback
            and rollback_result.rollback["return_code"] == 0
            and rollback_result.rollback_state
            and rollback_result.rollback_state["healthy"]
        )
        report["phases"].append(
            {
                "operation": "restart-docker-service",
                "parameters": {"service": "api"},
                "expected_outcome": "forced-post-check-failure-with-rollback",
                "success": rollback_passed,
                "rollback_result_sha256": _digest(rollback_document),
                "result": rollback_document,
            }
        )
        if not rollback_passed:
            raise RuntimeError("forced rollback rehearsal failed")

        report["success"] = True
        return_code = 0
    except (BrokerError, RuntimeError, StopIteration) as exc:
        report["harness_error"] = {
            "category": type(exc).__name__,
            "message": str(exc)[:500],
        }
        return_code = 1
    finally:
        report["ended_at"] = datetime.now(UTC).isoformat()
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_path.chmod(0o600)
        print(json.dumps({
            "report": str(report_path),
            "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "success": report["success"],
            "package_digest": package.manifest_digest,
        }, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
