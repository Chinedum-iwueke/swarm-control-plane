import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
import yaml
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.infrastructure import InfrastructureContract
from app.services.broker_tickets import canonical_ticket, issue_broker_ticket

TASK_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AGENT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
SECRET = "broker-ticket-test-secret-value-123456"


def task(*, restart: bool = False):
    return SimpleNamespace(
        id=TASK_ID,
        task_number="VM2-TEST-1",
        attempt_count=1,
        task_type=(
            "infrastructure_operation" if restart else "infrastructure_observation"
        ),
        risk_level=3 if restart else 0,
        plan_digest="a" * 64,
        input_contract={
            "runbook": "vm2-infrastructure",
            "runbook_version": "1.0.0",
            "operation": (
                "restart-control-plane-api" if restart else "observe-control-plane"
            ),
            "target": "vm2-control-plane",
            "parameters": {},
        },
        lease_expires_at=NOW + timedelta(minutes=5),
    )


def agent():
    return SimpleNamespace(id=AGENT_ID, machine="vm2-deployment")


def test_observation_ticket_is_signed_and_plan_bound() -> None:
    ticket = issue_broker_ticket(MagicMock(), task(), agent(), secret=SECRET, now=NOW)
    expected = hmac.new(
        SECRET.encode(), canonical_ticket(ticket.payload), hashlib.sha256
    ).hexdigest()
    assert ticket.signature == expected
    assert ticket.payload.contract.operation == "observe-control-plane"
    assert (
        ticket.payload.nonce
        == hashlib.sha256(f"{TASK_ID}:1:{'a' * 64}".encode()).hexdigest()
    )
    assert ticket.payload.expires_at == NOW + timedelta(seconds=60)


def test_restart_requires_consumed_approval_for_exact_plan() -> None:
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        status="approved",
        plan_digest="a" * 64,
        consumed_at=None,
        expires_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(HTTPException, match="consumed approval"):
        issue_broker_ticket(db, task(restart=True), agent(), secret=SECRET, now=NOW)

    db.scalar.return_value = SimpleNamespace(
        status="consumed",
        plan_digest="a" * 64,
        consumed_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    ticket = issue_broker_ticket(
        db, task(restart=True), agent(), secret=SECRET, now=NOW
    )
    assert ticket.payload.risk_level == 3
    assert ticket.payload.expires_at == NOW + timedelta(seconds=60)

    db.scalar.return_value = SimpleNamespace(
        status="consumed",
        plan_digest="a" * 64,
        consumed_at=NOW - timedelta(minutes=2),
        expires_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(HTTPException, match="consumed approval"):
        issue_broker_ticket(db, task(restart=True), agent(), secret=SECRET, now=NOW)


def test_postgres_staging_requires_consumed_approval() -> None:
    candidate = task()
    candidate.task_type = "infrastructure_operation"
    candidate.risk_level = 2
    candidate.input_contract = {
        "runbook": "vm2-postgres-deployment",
        "runbook_version": "1.0.0",
        "operation": "stage-invariance-postgres",
        "target": "vm2-invariance-postgres",
        "parameters": {},
    }
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException, match="consumed approval"):
        issue_broker_ticket(db, candidate, agent(), secret=SECRET, now=NOW)


def test_contract_rejects_commands_paths_and_unknown_parameters() -> None:
    document = task().input_contract
    document["parameters"] = {"command": ["docker", "restart"]}
    document["compose_file"] = "/etc/compose.yaml"
    with pytest.raises(ValidationError):
        InfrastructureContract.model_validate(document)


def test_risk_mismatch_is_rejected() -> None:
    candidate = task(restart=True)
    candidate.risk_level = 0
    with pytest.raises(HTTPException, match="risk three"):
        issue_broker_ticket(MagicMock(), candidate, agent(), secret=SECRET, now=NOW)


def test_packaged_ticket_requires_registered_approved_exact_digest() -> None:
    manifest = yaml.safe_load(
        (
            Path(__file__).parents[2]
            / "worker/runbook-packages/vm2-platform-operations.yaml"
        ).read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(
        json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    candidate = task()
    candidate.input_contract = {
        "runbook": "vm2-platform-operations",
        "runbook_version": "1.0.0",
        "operation": "verify-docker-service",
        "target": "vm2-production",
        "parameters": {"service": "api"},
        "package_name": "vm2-platform-operations",
        "package_version": "1.0.0",
        "package_digest": digest,
    }
    package = SimpleNamespace(id=UUID(int=3), manifest=manifest)
    db = MagicMock()
    db.scalar.side_effect = [
        package,
        SimpleNamespace(state="approved"),
        SimpleNamespace(recorded_at=NOW - timedelta(hours=1)),
    ]

    signed = issue_broker_ticket(db, candidate, agent(), secret=SECRET, now=NOW)

    assert signed.payload.contract.package_digest == digest
    assert signed.payload.contract.parameters == {"service": "api"}


def test_packaged_ticket_rejects_unapproved_or_unknown_parameter() -> None:
    candidate = task()
    candidate.input_contract = {
        "runbook": "vm2-platform-operations",
        "runbook_version": "1.0.0",
        "operation": "verify-docker-service",
        "target": "vm2-production",
        "parameters": {"service": "api", "command": "id"},
        "package_name": "vm2-platform-operations",
        "package_version": "1.0.0",
        "package_digest": "b" * 64,
    }
    package = SimpleNamespace(
        id=UUID(int=3),
        manifest={
            "rehearsal": {"max_evidence_age_hours": 168},
            "operations": [
                {
                    "name": "verify-docker-service",
                    "target_profile": "vm2-production",
                    "task_type": "infrastructure_observation",
                    "risk_level": 0,
                    "parameters": {
                        "service": {
                            "type": "string",
                            "required": True,
                            "allowed_values": ["api"],
                        }
                    },
                }
            ]
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [
        package,
        SimpleNamespace(state="approved"),
        SimpleNamespace(recorded_at=NOW - timedelta(hours=1)),
    ]
    with pytest.raises(HTTPException, match="Unknown operation parameter"):
        issue_broker_ticket(db, candidate, agent(), secret=SECRET, now=NOW)


def test_packaged_ticket_rejects_stale_rehearsal() -> None:
    candidate = task()
    candidate.input_contract = {
        "runbook": "vm2-platform-operations",
        "runbook_version": "1.0.0",
        "operation": "verify-redis",
        "target": "vm2-production",
        "parameters": {},
        "package_name": "vm2-platform-operations",
        "package_version": "1.0.0",
        "package_digest": "b" * 64,
    }
    package = SimpleNamespace(
        id=UUID(int=3),
        manifest={
            "rehearsal": {"max_evidence_age_hours": 24},
            "operations": [
                {
                    "name": "verify-redis",
                    "target_profile": "vm2-production",
                    "task_type": "infrastructure_observation",
                    "risk_level": 0,
                    "parameters": {},
                }
            ],
        },
    )
    db = MagicMock()
    db.scalar.side_effect = [
        package,
        SimpleNamespace(state="approved"),
        SimpleNamespace(recorded_at=NOW - timedelta(hours=25)),
    ]
    with pytest.raises(HTTPException, match="rehearsal is stale"):
        issue_broker_ticket(db, candidate, agent(), secret=SECRET, now=NOW)
