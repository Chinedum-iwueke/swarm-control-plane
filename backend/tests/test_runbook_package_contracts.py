import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest
import yaml
from fastapi import HTTPException

from app.schemas.runbook_package import (
    RunbookPackageCreate,
    RunbookPackageManifest,
    RunbookPromotionCreate,
)
from app.services.runbook_packages import (
    canonical_manifest,
    promote_runbook_package,
    verify_runbook_package,
)

ROOT = Path(__file__).parents[2] / "worker" / "runbook-packages"
PACKAGE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def manifest(name: str = "invariance-postgres-cutover") -> RunbookPackageManifest:
    return RunbookPackageManifest.model_validate(
        yaml.safe_load((ROOT / f"{name}.yaml").read_text(encoding="utf-8"))
    )


def test_repository_accepts_the_exact_worker_package_contracts() -> None:
    platform = manifest("vm2-platform-operations")
    cutover = manifest()
    assert len(platform.operations) == 7
    assert cutover.operations[-1].rollback is not None
    assert cutover.operations[-1].risk_level == 4


def test_runbook_package_digest_and_signature_are_verified() -> None:
    document = manifest()
    canonical = canonical_manifest(document)
    secret = "s" * 32
    payload = RunbookPackageCreate(
        manifest=document,
        manifest_digest=hashlib.sha256(canonical).hexdigest(),
        signature=hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest(),
        source_repository="swarm-control-plane",
        source_commit="a" * 40,
        created_by="founder-operator",
    )
    verify_runbook_package(payload, secret)
    with pytest.raises(HTTPException):
        verify_runbook_package(
            payload.model_copy(update={"manifest_digest": "0" * 64}),
            secret,
        )


def test_manifest_has_no_command_or_step_surface() -> None:
    assert "command" not in RunbookPackageManifest.model_fields
    assert "steps" not in RunbookPackageManifest.model_fields
    document = manifest().model_dump()
    document["operations"][0]["command"] = ["sudo", "anything"]
    with pytest.raises(ValueError):
        RunbookPackageManifest.model_validate(document)


def test_promotion_chain_is_sequential_and_digest_bound() -> None:
    package = SimpleNamespace(
        id=PACKAGE_ID,
        manifest_digest="a" * 64,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    db.refresh.side_effect = lambda record: setattr(record, "id", PACKAGE_ID)
    now = datetime(2026, 7, 31, tzinfo=UTC)

    draft = promote_runbook_package(
        db,
        package,
        RunbookPromotionCreate(state="draft", recorded_by="deployment-architect"),
        now=now,
    )
    assert draft.state == "draft"
    assert draft.previous_record_digest is None

    db.scalars.return_value.all.return_value = [draft]
    evidence = "b" * 64
    rehearsed = promote_runbook_package(
        db,
        package,
        RunbookPromotionCreate(
            state="rehearsed",
            evidence_digest=evidence,
            recorded_by="deployment-architect",
        ),
        now=now,
    )
    assert rehearsed.previous_record_digest == draft.record_digest

    db.scalars.return_value.all.return_value = [draft, rehearsed]
    with pytest.raises(HTTPException, match="Approval reference"):
        promote_runbook_package(
            db,
            package,
            RunbookPromotionCreate(
                state="approved",
                evidence_digest=evidence,
                recorded_by="founder-operator",
            ),
            now=now,
        )
    with pytest.raises(HTTPException, match="sequential"):
        promote_runbook_package(
            db,
            package,
            RunbookPromotionCreate(
                state="deployed",
                evidence_digest=evidence,
                approval_reference="M10B",
                recorded_by="deployment-architect",
            ),
            now=now,
        )
