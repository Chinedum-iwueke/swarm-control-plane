from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prompt_policy import (
    PromptPolicyBundle,
    PromptPolicyEvaluation,
    PromptPolicyEvent,
)
from app.schemas.prompt_policy import (
    PromptPolicyBundleCreate,
    PromptPolicyEvaluationCreate,
)

REQUIRED_ADVERSARIAL = {
    "prompt_injection",
    "secret_exfiltration",
    "malformed_output",
    "instruction_collision",
}


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def append_event(
    db: Session, bundle: PromptPolicyBundle, kind: str, actor: str, payload: dict
) -> None:
    previous = db.scalar(
        select(PromptPolicyEvent)
        .where(PromptPolicyEvent.bundle_id == bundle.id)
        .order_by(PromptPolicyEvent.sequence.desc())
        .limit(1)
    )
    sequence = (previous.sequence if previous else 0) + 1
    previous_digest = previous.event_digest if previous else None
    event_digest = digest(
        {
            "bundle_id": str(bundle.id),
            "sequence": sequence,
            "event_type": kind,
            "actor": actor,
            "payload": payload,
            "previous_digest": previous_digest,
        }
    )
    db.add(
        PromptPolicyEvent(
            bundle_id=bundle.id,
            sequence=sequence,
            event_type=kind,
            actor=actor,
            payload=payload,
            previous_digest=previous_digest,
            event_digest=event_digest,
        )
    )


def create_bundle(db: Session, payload: PromptPolicyBundleCreate) -> PromptPolicyBundle:
    document = payload.model_dump(mode="json")
    bundle = PromptPolicyBundle(
        bundle_key=payload.bundle_key,
        version=payload.version,
        purpose=payload.purpose,
        status="draft",
        schema_version="prompt-policy-bundle-v1.0.0",
        model_binding=payload.model_binding.model_dump(mode="json"),
        prompt_template=payload.prompt_template,
        policy=payload.policy,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        trust_labels=payload.trust_labels,
        allowed_tools=payload.allowed_tools,
        allowed_data_classes=payload.allowed_data_classes,
        bundle_digest=digest(document),
        created_by=payload.created_by,
    )
    db.add(bundle)
    db.flush()
    append_event(
        db,
        bundle,
        "bundle_registered",
        payload.created_by,
        {"bundle_digest": bundle.bundle_digest},
    )
    return bundle


def _validate(schema: dict, value: object, path: str = "$") -> list[str]:
    violations: list[str] = []
    expected = schema.get("type")
    checks = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    if expected in checks and (
        not isinstance(value, checks[expected])
        or expected in {"integer", "number"}
        and isinstance(value, bool)
    ):
        return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        violations.append(f"{path}: value is not in enum")
    if expected == "object" and isinstance(value, dict):
        required = set(schema.get("required", []))
        violations.extend(
            f"{path}.{key}: required" for key in sorted(required - set(value))
        )
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            violations.extend(
                f"{path}.{key}: additional property"
                for key in sorted(set(value) - set(properties))
            )
        for key in set(value) & set(properties):
            violations.extend(_validate(properties[key], value[key], f"{path}.{key}"))
    if expected == "array" and isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            violations.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            violations.append(f"{path}: more than maxItems")
        if "items" in schema:
            for index, item in enumerate(value):
                violations.extend(_validate(schema["items"], item, f"{path}[{index}]"))
    if (
        expected == "string"
        and isinstance(value, str)
        and "maxLength" in schema
        and len(value) > schema["maxLength"]
    ):
        violations.append(f"{path}: exceeds maxLength")
    return violations


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def evaluate(
    db: Session, bundle: PromptPolicyBundle, payload: PromptPolicyEvaluationCreate
) -> PromptPolicyEvaluation:
    violations = _validate(bundle.output_schema, payload.model_output)
    rendered = "\n".join(_strings(payload.model_output)).lower()
    for pattern in bundle.policy.get("forbidden_output_patterns", []):
        if pattern.lower() in rendered:
            violations.append(f"output contains forbidden pattern: {pattern}")
    if isinstance(payload.model_output, dict):
        forbidden_fields = set(bundle.policy.get("forbidden_output_fields", []))
        for field in sorted(forbidden_fields & set(payload.model_output)):
            violations.append(f"$.{field}: authority-bearing field is forbidden")
    expected_acceptance = payload.category == "valid_output"
    accepted = not violations
    passed = accepted == expected_acceptance
    if payload.category != "valid_output" and accepted:
        violations = ["adversarial fixture was not rejected"]
        passed = False
    fixture_digest = digest(
        {
            "category": payload.category,
            "fixture": payload.fixture,
            "model_output": payload.model_output,
        }
    )
    receipt = {
        "schema_version": "prompt-policy-evaluation-v1.0.0",
        "bundle_digest": bundle.bundle_digest,
        "category": payload.category,
        "accepted": accepted,
        "passed": passed,
        "violations": violations,
        "model_binding": bundle.model_binding,
    }
    evaluation = PromptPolicyEvaluation(
        bundle_id=bundle.id,
        category=payload.category,
        fixture_digest=fixture_digest,
        passed=passed,
        violations=violations,
        receipt=receipt,
        receipt_digest=digest(receipt),
        evaluated_by=payload.evaluated_by,
    )
    db.add(evaluation)
    db.flush()
    append_event(
        db,
        bundle,
        "evaluation_recorded",
        payload.evaluated_by,
        {
            "category": payload.category,
            "passed": passed,
            "receipt_digest": evaluation.receipt_digest,
        },
    )
    return evaluation


def promote(
    db: Session, bundle: PromptPolicyBundle, actor: str, target: str, reason: str
) -> None:
    allowed = {
        "draft": {"rehearsed"},
        "rehearsed": {"approved"},
        "approved": {"active"},
        "active": {"retired"},
    }
    if target not in allowed.get(bundle.status, set()):
        raise HTTPException(409, f"Invalid promotion from {bundle.status} to {target}.")
    evaluations = db.scalars(
        select(PromptPolicyEvaluation).where(
            PromptPolicyEvaluation.bundle_id == bundle.id
        )
    ).all()
    passed = {item.category for item in evaluations if item.passed}
    if target in {"approved", "active"}:
        if not REQUIRED_ADVERSARIAL.issubset(passed) or "valid_output" not in passed:
            raise HTTPException(
                409, "Required valid and adversarial evaluation evidence is incomplete."
            )
        if actor == bundle.created_by or not any(
            item.evaluated_by != bundle.created_by for item in evaluations
        ):
            raise HTTPException(
                409, "Independent review is required before approval or activation."
            )
    if target == "active":
        for prior in db.scalars(
            select(PromptPolicyBundle)
            .where(
                PromptPolicyBundle.bundle_key == bundle.bundle_key,
                PromptPolicyBundle.status == "active",
                PromptPolicyBundle.id != bundle.id,
            )
            .with_for_update()
        ).all():
            prior.status = "retired"
            prior.retired_at = datetime.now(UTC)
            append_event(
                db,
                prior,
                "bundle_superseded",
                actor,
                {"replacement_digest": bundle.bundle_digest},
            )
        bundle.activated_at = datetime.now(UTC)
    if target == "retired":
        bundle.retired_at = datetime.now(UTC)
    previous = bundle.status
    bundle.status = target
    append_event(
        db,
        bundle,
        "bundle_promoted",
        actor,
        {"from": previous, "to": target, "reason": reason},
    )


def serialize(db: Session, bundle: PromptPolicyBundle) -> dict:
    evaluations = db.scalars(
        select(PromptPolicyEvaluation)
        .where(PromptPolicyEvaluation.bundle_id == bundle.id)
        .order_by(PromptPolicyEvaluation.created_at)
    ).all()
    events = db.scalars(
        select(PromptPolicyEvent)
        .where(PromptPolicyEvent.bundle_id == bundle.id)
        .order_by(PromptPolicyEvent.sequence)
    ).all()
    return {
        "id": bundle.id,
        "bundle_key": bundle.bundle_key,
        "version": bundle.version,
        "purpose": bundle.purpose,
        "status": bundle.status,
        "schema_version": bundle.schema_version,
        "model_binding": bundle.model_binding,
        "trust_labels": bundle.trust_labels,
        "allowed_tools": bundle.allowed_tools,
        "allowed_data_classes": bundle.allowed_data_classes,
        "bundle_digest": bundle.bundle_digest,
        "created_by": bundle.created_by,
        "created_at": bundle.created_at,
        "activated_at": bundle.activated_at,
        "retired_at": bundle.retired_at,
        "evaluations": [
            {
                "id": str(item.id),
                "category": item.category,
                "passed": item.passed,
                "violations": item.violations,
                "receipt_digest": item.receipt_digest,
                "evaluated_by": item.evaluated_by,
            }
            for item in evaluations
        ],
        "events": [
            {
                "sequence": item.sequence,
                "event_type": item.event_type,
                "actor": item.actor,
                "payload": item.payload,
                "event_digest": item.event_digest,
            }
            for item in events
        ],
    }
