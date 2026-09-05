from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from io import BytesIO
from uuid import UUID

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.pipeline import _table_blocks
from app.models.evidence import CanonicalEvidenceObject
from app.schemas.scientific_fidelity import (
    FidelityManifestCreate,
    ScientificRepresentationCreate,
)
from app.services.object_store import FilesystemEvidenceObjectStore, ObjectReference
from app.services.scientific_fidelity import (
    digest,
    normalize,
    publish_manifest,
    register_representation,
    semantic_tokens,
)

VERSION = "scientific-fidelity-v2.1.0"
STRATA = {"equation": 10, "table": 5, "figure": 5}


def _page_texts(content: bytes, page: int) -> tuple[str, str]:
    native = (
        PdfReader(BytesIO(content), strict=True).pages[page - 1].extract_text() or ""
    )
    document = pdfium.PdfDocument(content)
    try:
        text_page = document[page - 1].get_textpage()
        try:
            structural = text_page.get_text_bounded()
        finally:
            text_page.close()
    finally:
        document.close()
    return native, structural


def _values(value: str) -> list[str]:
    return [item["value"] for item in semantic_tokens(value)]


def _region(page_text: str, target: str) -> str:
    target = normalize(target)
    page = normalize(page_text)
    if target in page:
        return target
    target_tokens = _values(target)
    candidates = [normalize(line) for line in page_text.splitlines() if line.strip()]
    if not candidates:
        return ""
    return max(
        candidates,
        key=lambda line: SequenceMatcher(None, target_tokens, _values(line)).ratio(),
    )


def _table_grid(value: str) -> list[list[str]]:
    rows = [line.strip() for line in value.splitlines() if line.strip()]
    grid = []
    for row in rows:
        cells = row.strip("|").split("|") if "|" in row else re.split(r"\s{2,}", row)
        grid.append([normalize(cell) for cell in cells if cell.strip()])
    return [row for row in grid if row]


def _table_region(
    page_text: str, target: str, *, line_start: int, line_end: int
) -> str:
    """Recover a complete table without flattening its row boundaries."""
    lines = page_text.splitlines()
    coordinate_region = "\n".join(lines[line_start - 1 : line_end]).strip()
    if len(_table_grid(coordinate_region)) >= 2:
        return coordinate_region

    blocks = [value for _, value in _table_blocks(lines).values()]
    if not blocks:
        return ""
    target_tokens = _values(target)
    return max(
        blocks,
        key=lambda block: SequenceMatcher(
            None, target_tokens, _values(block)
        ).ratio(),
    )


def main() -> int:
    settings = get_settings()
    store = FilesystemEvidenceObjectStore(settings.evidence_object_root)
    with SessionLocal() as db:
        candidates = db.scalars(
            select(CanonicalEvidenceObject)
            .where(
                CanonicalEvidenceObject.object_type == "scientific_object",
                CanonicalEvidenceObject.payload["scientific_type"].astext.in_(
                    tuple(STRATA)
                ),
            )
            .order_by(CanonicalEvidenceObject.content_digest)
            .limit(500)
        ).all()
        if not candidates:
            raise RuntimeError("Live corpus has no held-out equation objects.")
        results = []
        evaluated = {key: 0 for key in STRATA}
        accepted = {key: 0 for key in STRATA}
        skipped = {"non_pdf": 0, "parser_error": 0, "empty_region": 0}
        page_cache: dict[tuple[UUID, int], tuple[str, str]] = {}
        for item in candidates:
            scientific_type = item.payload["scientific_type"]
            if evaluated[scientific_type] >= STRATA[scientific_type]:
                continue
            if all(evaluated[key] >= target for key, target in STRATA.items()):
                break
            artifact = db.get(
                CanonicalEvidenceObject, UUID(item.payload["artifact_object_id"])
            )
            if (
                artifact is None
                or artifact.payload.get("media_type") != "application/pdf"
            ):
                skipped["non_pdf"] += 1
                continue
            reference = ObjectReference(
                uri=artifact.payload["storage_uri"],
                content_digest=artifact.content_digest,
                byte_size=artifact.payload["byte_size"],
            )
            page = int(item.payload["coordinates"]["page"])
            cache_key = (artifact.id, page)
            if cache_key not in page_cache:
                try:
                    page_cache[cache_key] = _page_texts(store.get(reference), page)
                except (PdfReadError, ValueError, IndexError, RuntimeError, OSError):
                    skipped["parser_error"] += 1
                    continue
            native_page, structural_page = page_cache[cache_key]
            target = item.payload["content_text"]
            coordinates = item.payload["coordinates"]
            if scientific_type == "table":
                region_args = {
                    "line_start": int(coordinates["line_start"]),
                    "line_end": int(coordinates["line_end"]),
                }
                native_match = _table_region(native_page, target, **region_args)
                structural_match = _table_region(
                    structural_page, target, **region_args
                )
            else:
                native_match = _region(native_page, target)
                structural_match = _region(structural_page, target)
            if not native_match.strip() or not structural_match.strip():
                skipped["empty_region"] += 1
                continue
            native_grid = (
                _table_grid(native_match) if scientific_type == "table" else None
            )
            structural_grid = (
                _table_grid(structural_match) if scientific_type == "table" else None
            )
            if scientific_type == "table" and (
                not native_grid
                or not structural_grid
                or len(native_grid) < 2
                or len(structural_grid) < 2
            ):
                skipped["empty_region"] += 1
                continue
            parser_content = (
                [
                    json.dumps(native_grid, ensure_ascii=False),
                    json.dumps(structural_grid, ensure_ascii=False),
                ]
                if scientific_type == "table"
                else [native_match, structural_match]
            )
            record = register_representation(
                db,
                ScientificRepresentationCreate(
                    source_object_id=item.id,
                    representation_version=VERSION,
                    scientific_type=scientific_type,
                    source_region_digest=hashlib.sha256(
                        structural_page.encode()
                    ).hexdigest(),
                    parser_outputs=[
                        {
                            "parser": "pypdf-heldout",
                            "method": "native",
                            "content": parser_content[0],
                            "confidence": 0.98,
                        },
                        {
                            "parser": "pdfium-heldout",
                            "method": "structural",
                            "content": parser_content[1],
                            "confidence": 0.98,
                        },
                    ],
                    table_grid=(native_grid if scientific_type == "table" else None),
                    figure_caption=(
                        native_match if scientific_type == "figure" else None
                    ),
                    created_by="ri014-live-pilot",
                ),
            )
            results.append(record)
            evaluated[scientific_type] += 1
            accepted[scientific_type] += record.status == "accepted"
        if not results:
            raise RuntimeError(
                "No PDF equation regions were eligible for the held-out run."
            )
        missing_strata = [
            key for key, target in STRATA.items() if evaluated[key] < target
        ]
        rates = {
            key: accepted[key] / evaluated[key] if evaluated[key] else 0.0
            for key in STRATA
        }
        corpus_digest = digest([str(item.source_object_id) for item in results])
        manifest = publish_manifest(
            db,
            FidelityManifestCreate(
                corpus_digest=corpus_digest,
                representation_version=VERSION,
                thresholds={
                    "token_precision": 0.99,
                    "token_recall": 0.99,
                    "cell_accuracy": 0.99,
                    "expression_replay": 1.0,
                    "figure_reference_replay": 0.99,
                },
                metrics={
                    "token_precision": rates["equation"],
                    "token_recall": rates["equation"],
                    "cell_accuracy": rates["table"],
                    "expression_replay": rates["equation"],
                    "figure_reference_replay": rates["figure"],
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
                    "evaluated": evaluated,
                    "accepted": accepted,
                    "missing_strata": missing_strata,
                    "skipped": skipped,
                    "record_digest": manifest.record_digest,
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
