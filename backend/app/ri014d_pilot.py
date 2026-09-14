from __future__ import annotations

import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.evidence import CanonicalEvidenceObject
from app.models.scientific_fidelity import (
    ScientificAssuranceReceipt,
    ScientificRepresentation,
)
from app.schemas.scientific_fidelity import ScientificAssuranceRequestCreate
from app.services.scientific_assurance import request_assurance
from app.services.scientific_fidelity import ScientificFidelityConflict, digest


def main() -> int:
    with SessionLocal() as db:
        representations = list(
            db.scalars(
                select(ScientificRepresentation)
                .where(
                    ScientificRepresentation.scientific_type == "equation",
                    ScientificRepresentation.status == "accepted",
                )
                .order_by(ScientificRepresentation.created_at.desc())
            ).all()
        )
        selected = next(
            (
                item
                for item in representations
                if (source := db.get(CanonicalEvidenceObject, item.source_object_id))
                and source.payload.get("content_text")
            ),
            None,
        )
        if selected is None:
            raise RuntimeError("No accepted, source-replayable equation is available.")
        payload = ScientificAssuranceRequestCreate(
            representation_id=selected.id,
            expression=selected.normalized_content,
            purpose="RI-014D production source-binding and cache replay",
            requested_by="ri014d-production-pilot",
        )
        first = request_assurance(db, payload)
        second = request_assurance(db, payload)
        db.flush()
        receipt = db.scalar(
            select(ScientificAssuranceReceipt).where(
                ScientificAssuranceReceipt.request_id == first.id
            )
        )
        mismatch_rejected = False
        try:
            request_assurance(
                db,
                payload.model_copy(
                    update={"expression": f"{selected.normalized_content} + 1"}
                ),
            )
        except ScientificFidelityConflict:
            mismatch_rejected = True
        if receipt is None or first.id != second.id or not mismatch_rejected:
            raise RuntimeError("RI-014D production assurance gates did not close.")
        report = {
            "schema_version": "ri014d-production-pilot-v1.0.0",
            "success": True,
            "request_id": str(first.id),
            "receipt_digest": receipt.record_digest,
            "assurance_level": receipt.assurance_level,
            "source_object_id": str(receipt.source_object_id),
            "expression_digest": receipt.expression_digest,
            "cache_reused": first.id == second.id,
            "mismatched_expression_rejected": mismatch_rejected,
            "capital_or_order_authority": False,
            "claim_boundary": receipt.claim_boundary,
        }
        report["report_digest"] = digest(report)
        db.commit()
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
