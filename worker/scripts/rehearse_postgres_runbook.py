#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from swarm_worker.infrastructure.broker import InfrastructureBroker
from swarm_worker.models import BrokerTicketPayload, BrokerTicketResponse

UTC = timezone.utc
SECRET = "vm2-postgres-rehearsal-secret-value-2026"
TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AGENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OPERATIONS = (
    ("preflight-invariance-postgres", 0, "infrastructure_observation"),
    ("stage-invariance-postgres", 2, "infrastructure_operation"),
    ("start-invariance-postgres-private", 3, "infrastructure_operation"),
    ("initialize-invariance-schema", 3, "infrastructure_operation"),
    ("configure-invariance-backups", 3, "infrastructure_operation"),
    ("verify-invariance-postgres", 0, "infrastructure_observation"),
    ("prepare-invariance-cutover", 0, "infrastructure_observation"),
)


def ticket(operation: str, risk: int, task_type: str, attempt: int) -> dict:
    now = datetime.now(UTC)
    payload = BrokerTicketPayload(
        schema_version=1,
        task_id=TASK_ID,
        task_number=f"REHEARSAL-{attempt:02d}",
        attempt_number=attempt,
        agent_id=AGENT_ID,
        machine="vm2-deployment",
        task_type=task_type,
        risk_level=risk,
        plan_digest=hashlib.sha256(operation.encode()).hexdigest(),
        contract={
            "runbook": "vm2-postgres-deployment",
            "runbook_version": "1.0.0",
            "operation": operation,
            "target": "vm2-invariance-postgres",
            "parameters": {},
        },
        nonce=hashlib.sha256(f"{operation}:{attempt}".encode()).hexdigest(),
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("/srv/invariance/postgres"),
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/srv/invariance/rehearsal-source/invariance_research"),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("/var/lib/invariance-swarm-rehearsal"),
    )
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("the parity rehearsal must run as root")

    marker = args.state / "DISPOSABLE_REHEARSAL"
    if marker.read_text(encoding="utf-8").strip() != "vm2-postgres":
        parser.error("disposable rehearsal marker is unavailable")
    docker_config = Path(
        "/run/invariance-swarm-infrastructure/docker-config"
    )
    docker_config.mkdir(parents=True, exist_ok=True, mode=0o700)
    docker_config.chmod(0o700)

    broker = InfrastructureBroker(
        secret=SECRET,
        ledger_path=args.state / "consumed.json",
        effective_uid=0,
        runtime_path=args.state / "control-plane-runtime",
        backup_path=args.state / "control-plane-runtime" / "backups",
        postgres_root=args.root,
        postgres_bind_address="127.0.0.1",
        research_repository=args.source,
        systemd_path=Path("/etc/systemd/system"),
    )
    report: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "docker_target": "vm2-parity",
        "phases": [],
        "success": False,
    }
    report_path = args.state / "report.json"
    try:
        for attempt, (operation, risk, task_type) in enumerate(OPERATIONS, 1):
            result = broker.execute(ticket(operation, risk, task_type, attempt))
            phase = {
                "operation": operation,
                "success": result.success,
                "error": result.error,
                "started_at": result.started_at.isoformat(),
                "ended_at": result.ended_at.isoformat(),
            }
            report["phases"].append(phase)  # type: ignore[union-attr]
            report_path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if not result.success:
                return 1
        report["success"] = True
        report["ended_at"] = datetime.now(UTC).isoformat()
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
    finally:
        report_path.chmod(0o600)


if __name__ == "__main__":
    raise SystemExit(main())
