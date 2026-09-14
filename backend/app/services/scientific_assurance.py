from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.evaluator_routing import EvaluationIndependenceReceipt
from app.models.evidence import CanonicalEvidenceObject
from app.models.scientific_fidelity import (
    ScientificAssuranceAttempt,
    ScientificAssuranceReceipt,
    ScientificAssuranceRequest,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import (
    ScientificAssuranceAttemptCreate,
    ScientificAssuranceRequestCreate,
)
from app.services.scientific_fidelity import (
    ScientificFidelityConflict,
    _accepted_representation_ids,
    digest,
    expression_tree,
    normalize,
    semantic_tokens,
)


def expression_digest(expression: str) -> str:
    return digest("".join(normalize(expression).split()))


def request_assurance(
    db: Session, payload: ScientificAssuranceRequestCreate
) -> ScientificAssuranceRequest:
    representation = db.get(ScientificRepresentation, payload.representation_id)
    if representation is None or representation.scientific_type != "equation":
        raise ScientificFidelityConflict(
            "Assurance requires an equation representation."
        )
    source = db.get(CanonicalEvidenceObject, representation.source_object_id)
    if source is None or source.object_type != "scientific_object":
        raise ScientificFidelityConflict(
            "Assurance requires a canonical scientific source object."
        )
    requested_digest = expression_digest(payload.expression)
    represented_digest = expression_digest(representation.normalized_content)
    if requested_digest != represented_digest:
        raise ScientificFidelityConflict(
            "Requested expression does not match the source-bound representation."
        )
    material = {
        "representation_digest": representation.record_digest,
        "source_region_digest": representation.source_region_digest,
        "expression_digest": requested_digest,
        "required_level": payload.required_level,
        "policy_version": payload.policy_version,
    }
    cache_key = digest(material)
    existing = db.scalar(
        select(ScientificAssuranceRequest).where(
            ScientificAssuranceRequest.cache_key == cache_key
        )
    )
    if existing:
        return existing
    request = ScientificAssuranceRequest(
        representation_id=representation.id,
        expression=normalize(payload.expression),
        expression_digest=requested_digest,
        purpose=payload.purpose,
        required_level=payload.required_level,
        policy_version=payload.policy_version,
        status="pending",
        cache_key=cache_key,
        requested_by=payload.requested_by,
    )
    try:
        with db.begin_nested():
            db.add(request)
            db.flush()
    except IntegrityError:
        request = db.scalar(
            select(ScientificAssuranceRequest).where(
                ScientificAssuranceRequest.cache_key == cache_key
            )
        )
        if request is None:
            raise
    for output in representation.parser_outputs:
        _record_attempt(
            db,
            request,
            representation,
            ScientificAssuranceAttemptCreate(
                provider_family=f"representation:{output['parser']}",
                extractor_version=representation.representation_version,
                produced_by=representation.created_by,
                content=output["content"],
                semantic_payload={},
            ),
        )
    finalize_assurance(db, request.id)
    return request


def submit_attempt(
    db: Session,
    request_id,
    payload: ScientificAssuranceAttemptCreate,
) -> ScientificAssuranceAttempt:
    request = db.get(ScientificAssuranceRequest, request_id)
    if request is None:
        raise ScientificFidelityConflict("Scientific assurance request not found.")
    if request.status in {"verified", "abstained"}:
        raise ScientificFidelityConflict("Scientific assurance request is terminal.")
    representation = db.get(ScientificRepresentation, request.representation_id)
    attempt = _record_attempt(db, request, representation, payload)
    finalize_assurance(db, request.id)
    return attempt


def _record_attempt(db, request, representation, payload):
    existing = db.scalar(
        select(ScientificAssuranceAttempt).where(
            ScientificAssuranceAttempt.request_id == request.id,
            ScientificAssuranceAttempt.provider_family == payload.provider_family,
            ScientificAssuranceAttempt.extractor_version == payload.extractor_version,
        )
    )
    tree, complete = expression_tree(semantic_tokens(payload.content))
    checks = {
        "semantic_token_match": expression_digest(payload.content)
        == request.expression_digest,
        "ast_complete": complete,
        "ast_match": tree == representation.semantic_payload.get("expression_tree"),
        "source_region_bound": bool(representation.source_region_digest),
    }
    outcome = "passed" if all(checks.values()) else "mismatch"
    canonical_semantic = {"expression_tree": tree}
    if payload.semantic_payload and payload.semantic_payload != canonical_semantic:
        raise ScientificFidelityConflict(
            "Submitted semantic payload does not match the deterministic parse."
        )
    review_payload_digest = digest(
        {
            "content": normalize(payload.content),
            "semantic_payload": canonical_semantic,
        }
    )
    independence_receipt = (
        db.scalar(
            select(EvaluationIndependenceReceipt).where(
                EvaluationIndependenceReceipt.receipt_digest
                == payload.independence_receipt_digest,
                EvaluationIndependenceReceipt.subject_digest == request.cache_key,
                EvaluationIndependenceReceipt.verdict == "independence_demonstrated",
            )
        )
        if payload.independence_receipt_digest
        else None
    )
    routed_review_digests = (
        {
            item.get("review_digest")
            for item in independence_receipt.assertion.get("assignments", [])
        }
        if independence_receipt
        else set()
    )
    independent = bool(
        independence_receipt
        and payload.independent_review_digest == review_payload_digest
        and payload.independent_review_digest in routed_review_digests
        and payload.produced_by != representation.created_by
        and not payload.provider_family.startswith("representation:")
    )
    material = {
        "request_id": str(request.id),
        "provider_family": payload.provider_family,
        "extractor_version": payload.extractor_version,
        "produced_by": payload.produced_by,
        "independence_receipt_digest": payload.independence_receipt_digest,
        "independent_review_digest": payload.independent_review_digest,
        "independent_of_representation": independent,
        "content": normalize(payload.content),
        "semantic_payload": canonical_semantic,
        "checks": checks,
        "outcome": outcome,
    }
    attempt_digest = digest(material)
    if existing:
        if existing.attempt_digest != attempt_digest:
            raise ScientificFidelityConflict("Assurance attempt is immutable.")
        return existing
    attempt = ScientificAssuranceAttempt(**material, attempt_digest=attempt_digest)
    try:
        with db.begin_nested():
            db.add(attempt)
            db.flush()
    except IntegrityError:
        attempt = db.scalar(
            select(ScientificAssuranceAttempt).where(
                ScientificAssuranceAttempt.request_id == request.id,
                ScientificAssuranceAttempt.provider_family
                == payload.provider_family,
                ScientificAssuranceAttempt.extractor_version
                == payload.extractor_version,
            )
        )
        if attempt is None or attempt.attempt_digest != attempt_digest:
            raise ScientificFidelityConflict("Assurance attempt is immutable.")
    return attempt


def finalize_assurance(db: Session, request_id) -> ScientificAssuranceReceipt | None:
    request = db.get(ScientificAssuranceRequest, request_id)
    if request is None:
        raise ScientificFidelityConflict("Scientific assurance request not found.")
    existing = db.scalar(
        select(ScientificAssuranceReceipt).where(
            ScientificAssuranceReceipt.request_id == request.id
        )
    )
    if existing:
        return existing
    representation = db.get(ScientificRepresentation, request.representation_id)
    source = db.get(CanonicalEvidenceObject, representation.source_object_id)
    attempts = list(
        db.scalars(
            select(ScientificAssuranceAttempt)
            .where(ScientificAssuranceAttempt.request_id == request.id)
            .order_by(ScientificAssuranceAttempt.attempt_digest)
        ).all()
    )
    passed = [item for item in attempts if item.outcome == "passed"]
    provider_families = {item.provider_family for item in passed}
    source_bound = bool(
        source
        and source.object_type == "scientific_object"
        and source.content_digest
        and source.payload.get("content_text")
        and expression_digest(source.payload["content_text"])
        == request.expression_digest
    )
    checks = {
        "source_object_bound": source_bound,
        "representation_accepted": representation.id
        in _accepted_representation_ids(db),
        "two_provider_agreement": len(provider_families) >= 2,
        "lossless_ast_complete": bool(
            representation.semantic_payload.get("expression_tree")
            and not any(
                item.get("kind") == "semantic_parse_incomplete"
                for item in representation.uncertainties
            )
        ),
        "all_outputs_agree": bool(attempts)
        and all(item.outcome == "passed" for item in attempts),
    }
    decision, assurance_level = assurance_decision(
        request.required_level, checks, attempts
    )
    if decision == "awaiting_independent_attempt":
        request.status = decision
        return None
    if decision == "abstained":
        independent_mismatch = any(
            item.outcome == "mismatch"
            and item.independence_receipt_digest
            for item in attempts
        )
        return _issue_receipt(
            db,
            request,
            representation,
            source,
            attempts,
            checks,
            status="abstained",
            assurance_level="unverified",
            limitations=(
                ["Independent extraction materially disagreed."]
                if independent_mismatch
                else [
                    f"Failed deterministic checks: {', '.join(key for key, value in checks.items() if not value)}."
                ]
            ),
        )
    return _issue_receipt(
        db,
        request,
        representation,
        source,
        attempts,
        checks,
        status="verified",
        assurance_level=assurance_level,
        limitations=[
            "Verification is scoped to transcription, token preservation, AST completeness, and source binding; it does not prove the source equation is scientifically valid."
        ],
    )


def _issue_receipt(
    db,
    request,
    representation,
    source,
    attempts,
    checks,
    *,
    status,
    assurance_level,
    limitations,
):
    material = {
        "request_id": str(request.id),
        "representation_id": str(representation.id),
        "source_object_id": str(source.id),
        "source_content_digest": source.content_digest,
        "source_region_digest": representation.source_region_digest,
        "expression_digest": request.expression_digest,
        "assurance_level": assurance_level,
        "status": status,
        "deterministic_checks": checks,
        "attempt_digests": [item.attempt_digest for item in attempts],
        "limitations": limitations,
        "claim_boundary": (
            "The exact source-bound expression is safe for deterministic calculation at the stated assurance level; scientific validity remains a separate claim."
            if status == "verified"
            else "The expression is not calculation-bearing; failed assurance evidence is retained for correction or a new representation version."
        ),
        "issued_by": "ri014d-deterministic-assurance",
    }
    receipt = ScientificAssuranceReceipt(**material, record_digest=digest(material))
    try:
        with db.begin_nested():
            db.add(receipt)
            request.status = status
            db.flush()
    except IntegrityError:
        receipt = db.scalar(
            select(ScientificAssuranceReceipt).where(
                ScientificAssuranceReceipt.request_id == request.id
            )
        )
        if receipt is None:
            raise
        request.status = receipt.status
    return receipt


def assurance_decision(
    required_level: str, checks: dict, attempts: list
) -> tuple[str, str]:
    if not all(checks.values()):
        return "abstained", "unverified"
    independent_pass = any(
        item.outcome == "passed" and item.independent_of_representation
        for item in attempts
    )
    if required_level == "independently_verified" and not independent_pass:
        independent_mismatch = any(
            item.outcome == "mismatch" and item.independence_receipt_digest
            for item in attempts
        )
        return (
            ("abstained", "unverified")
            if independent_mismatch
            else ("awaiting_independent_attempt", "unverified")
        )
    return (
        "verified",
        "independently_verified" if independent_pass else "machine_verified",
    )


def assurance_overview(db: Session) -> dict:
    requests = list(db.scalars(select(ScientificAssuranceRequest)).all())
    receipts = list(db.scalars(select(ScientificAssuranceReceipt)).all())
    counts = {
        key: 0
        for key in (
            "pending",
            "awaiting_independent_attempt",
            "needs_attention",
            "verified",
            "abstained",
        )
    }
    for item in requests:
        counts[item.status] = counts.get(item.status, 0) + 1
    document = {
        "schema_version": "ri014d-assurance-overview-v1.0.0",
        "counts": counts,
        "requests": requests,
        "receipts": receipts,
        "claim_boundary": "Only terminal verified receipts authorize equation-dependent calculation; unresolved requests require no routine human action unless marked needs_attention.",
    }
    return document


def receipt_matches_equation(
    db: Session,
    receipt_digest: str,
    *,
    source_object_id,
    source_content_digest: str,
    expression: str,
    required_level: str,
) -> bool:
    receipt = db.scalar(
        select(ScientificAssuranceReceipt).where(
            ScientificAssuranceReceipt.record_digest == receipt_digest
        )
    )
    if receipt is None or receipt.status != "verified":
        return False
    levels = {"machine_verified": 1, "independently_verified": 2}
    return bool(
        receipt.source_object_id == source_object_id
        and receipt.source_content_digest == source_content_digest
        and receipt.expression_digest == expression_digest(expression)
        and levels.get(receipt.assurance_level, 0) >= levels[required_level]
    )


def assure_source_equation(
    db: Session,
    *,
    source_object_id,
    source_content_digest: str,
    expression: str,
    purpose: str,
    requested_by: str,
) -> ScientificAssuranceReceipt | None:
    source = db.get(CanonicalEvidenceObject, source_object_id)
    if source is None or source.content_digest != source_content_digest:
        return None
    representations = list(
        db.scalars(
            select(ScientificRepresentation)
            .where(
                ScientificRepresentation.source_object_id == source_object_id,
                ScientificRepresentation.scientific_type == "equation",
            )
            .order_by(ScientificRepresentation.created_at.desc())
        ).all()
    )
    representation = next(
        (
            item
            for item in representations
            if expression_digest(item.normalized_content)
            == expression_digest(expression)
        ),
        None,
    )
    if representation is None:
        return None
    request = request_assurance(
        db,
        ScientificAssuranceRequestCreate(
            representation_id=representation.id,
            expression=expression,
            purpose=purpose,
            required_level="machine_verified",
            requested_by=requested_by,
        ),
    )
    receipt = finalize_assurance(db, request.id)
    return receipt if receipt and receipt.status == "verified" else None
