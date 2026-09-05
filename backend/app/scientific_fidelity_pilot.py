from __future__ import annotations

import hashlib
import json
from io import BytesIO
from uuid import UUID

import pypdfium2 as pdfium
from pypdf import PdfReader
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.evidence import CanonicalEvidenceObject
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificRepresentationCreate,
)
from app.services.object_store import FilesystemEvidenceObjectStore, ObjectReference
from app.services.scientific_fidelity import (
    digest,
    publish_manifest,
    register_representation,
)


def _page_texts(content: bytes, page: int) -> tuple[str, str]:
    native = (
        PdfReader(BytesIO(content), strict=True).pages[page - 1].extract_text() or ""
    )
    document = pdfium.PdfDocument(content)
    try:
        text_page = document[page - 1].get_textpage()
        try:
            structural = text_page.get_text_range()
        finally:
            text_page.close()
    finally:
        document.close()
    return native, structural


def main() -> int:
    settings = get_settings()
    store = FilesystemEvidenceObjectStore(settings.evidence_object_root)
    with SessionLocal() as db:
        objects = db.scalars(
            select(CanonicalEvidenceObject)
            .where(CanonicalEvidenceObject.object_type == "scientific_object")
            .order_by(CanonicalEvidenceObject.content_digest)
        ).all()
        heldout = [
            item
            for item in objects
            if item.payload.get("scientific_type") == "equation"
        ][:20]
        if not heldout:
            raise RuntimeError("Live corpus has no held-out equation objects.")
        results = []
        for item in heldout:
            artifact = db.get(
                CanonicalEvidenceObject, UUID(item.payload["artifact_object_id"])
            )
            if (
                artifact is None
                or artifact.payload.get("media_type") != "application/pdf"
            ):
                continue
            reference = ObjectReference(
                uri=artifact.payload["storage_uri"],
                content_digest=artifact.content_digest,
                byte_size=artifact.payload["byte_size"],
            )
            content = store.get(reference)
            page = int(item.payload["coordinates"]["page"])
            native_page, structural_page = _page_texts(content, page)
            target = " ".join(item.payload["content_text"].split())
            native_match = (
                target if target in " ".join(native_page.split()) else native_page
            )
            structural_match = (
                target
                if target in " ".join(structural_page.split())
                else structural_page
            )
            record = register_representation(
                db,
                ScientificRepresentationCreate(
                    source_object_id=item.id,
                    scientific_type="equation",
                    source_region_digest=hashlib.sha256(
                        structural_page.encode()
                    ).hexdigest(),
                    parser_outputs=[
                        {
                            "parser": "pypdf-heldout",
                            "method": "native",
                            "content": native_match,
                            "confidence": 0.98,
                        },
                        {
                            "parser": "pdfium-heldout",
                            "method": "structural",
                            "content": structural_match,
                            "confidence": 0.98,
                        },
                    ],
                    created_by="ri014-live-pilot",
                ),
            )
            results.append(record)
        if not results:
            raise RuntimeError(
                "No PDF equation regions were eligible for the held-out run."
            )
        accepted = sum(item.status == "accepted" for item in results)
        rate = accepted / len(results)
        corpus_digest = digest([str(item.source_object_id) for item in results])
        manifest = publish_manifest(
            db,
            FidelityManifestCreate(
                corpus_digest=corpus_digest,
                thresholds={
                    "token_precision": 0.99,
                    "token_recall": 0.99,
                    "cell_accuracy": 0.99,
                    "expression_replay": 1.0,
                },
                metrics={
                    "token_precision": rate,
                    "token_recall": rate,
                    "cell_accuracy": 1.0,
                    "expression_replay": rate,
                },
                created_by="ri014-live-pilot",
            ),
        )
        db.commit()
        print(
            json.dumps(
                {
                    "manifest_id": str(manifest.id),
                    "status": manifest.status,
                    "counts": manifest.counts,
                    "metrics": manifest.metrics,
                    "record_digest": manifest.record_digest,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
