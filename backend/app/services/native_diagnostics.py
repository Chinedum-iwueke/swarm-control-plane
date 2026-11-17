"""Verify receipt custody only; Bulletproof owns diagnostic computation."""
import re

from app.services.graph import digest_document


def verify_diagnostic(receipt, request, catalog, source, subject):
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "native-diagnostic-receipt-v1":
        raise ValueError("invalid native diagnostic receipt")
    if (receipt.get("request_digest") != digest_document(request)
            or receipt.get("evidence_catalog_digest") != digest_document(catalog)
            or receipt.get("source_commit") != source or request.get("source_commit") != source
            or receipt.get("subject_digest") != subject or request.get("subject_digest") != subject
            or receipt.get("tool") != request.get("tool")
            or receipt.get("receipt_digest") != digest_document({k: v for k, v in receipt.items() if k != "receipt_digest"})):
        raise ValueError("native diagnostic binding mismatch")
    for flag in ("execution_authority", "scientific_certification", "market_data_used"):
        if receipt.get(flag) is not False:
            raise ValueError("diagnostic cannot grant authority or claim observed market evidence")
    implementations = receipt.get("implementation_digests")
    if not isinstance(implementations, dict) or not implementations or any(
            not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v) for v in implementations.values()):
        raise ValueError("missing diagnostic implementation binding")
    result = receipt.get("result")
    if not isinstance(result, dict):
        raise ValueError("invalid diagnostic result")
    def check_claims(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"scientific_certification", "scientific_approval", "execution_authority"} and item is not False:
                    raise ValueError("nested diagnostic authority claim")
                if key == "status" and item in ("approved", "certified"):
                    raise ValueError("diagnostic approval claim")
                check_claims(item)
        elif isinstance(value, list):
            for item in value:
                check_claims(item)
    check_claims(result)
    kind = "synthetic_calibration" if receipt["tool"] == "residual_calibration_v1" and result.get("status") == "diagnostic_only" else "design_diagnostic"
    if receipt.get("evidence_kind") != kind:
        raise ValueError("diagnostic evidence kind mismatch")
    return receipt
