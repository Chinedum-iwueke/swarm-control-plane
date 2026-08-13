from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject


class PdfSanitizationError(ValueError):
    pass


@dataclass(frozen=True)
class PdfSanitizationResult:
    content: bytes
    original_digest: str
    sanitized_digest: str
    page_count: int
    text_digest: str
    visual_sample_digest: str
    visual_sample_pages: list[int]
    removed: dict[str, int]


def sanitize_pdf(content: bytes) -> PdfSanitizationResult:
    """Create an inert PDF and prove that its extracted text did not change."""

    original_digest = hashlib.sha256(content).hexdigest()
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        original_pages = [_normalized_text(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise PdfSanitizationError("original PDF cannot be parsed for safe recovery") from exc
    if not original_pages:
        raise PdfSanitizationError("original PDF has no pages")

    removed = {"annotations": 0, "page_actions": 0, "forms": 0, "names": 0}
    original_root = _object(reader.trailer.get("/Root"))
    if isinstance(original_root, DictionaryObject):
        removed["page_actions"] += sum(
            name in original_root for name in ("/OpenAction", "/AA")
        )
        removed["forms"] += int("/AcroForm" in original_root)
        names = _object(original_root.get("/Names"))
        if isinstance(names, DictionaryObject):
            removed["names"] += sum(
                name in names for name in ("/JavaScript", "/EmbeddedFiles")
            )
    writer = PdfWriter()
    for page in reader.pages:
        if "/Annots" in page:
            annotations = page.get("/Annots")
            removed["annotations"] += len(annotations) if isinstance(annotations, ArrayObject) else 1
            del page[NameObject("/Annots")]
        if "/AA" in page:
            del page[NameObject("/AA")]
            removed["page_actions"] += 1
        writer.add_page(page)

    root = writer.root_object
    for name in ("/OpenAction", "/AA"):
        if name in root:
            del root[NameObject(name)]
    if "/AcroForm" in root:
        del root[NameObject("/AcroForm")]
    if "/Names" in root:
        del root[NameObject("/Names")]
    writer.add_metadata({"/Producer": "Hermes inert PDF sanitizer v1"})

    output = BytesIO()
    writer.write(output)
    sanitized = output.getvalue()
    try:
        check = PdfReader(BytesIO(sanitized), strict=True)
        sanitized_pages = [_normalized_text(page.extract_text() or "") for page in check.pages]
    except Exception as exc:
        raise PdfSanitizationError("sanitized PDF failed strict parsing") from exc
    if len(sanitized_pages) != len(original_pages):
        raise PdfSanitizationError("sanitized PDF page count changed")
    original_text_digest = _pages_digest(original_pages)
    if _pages_digest(sanitized_pages) != original_text_digest:
        raise PdfSanitizationError("sanitized PDF extracted text changed")
    visual_pages = sorted({0, len(original_pages) // 2, len(original_pages) - 1})
    original_visual_digest = _visual_digest(content, visual_pages)
    if _visual_digest(sanitized, visual_pages) != original_visual_digest:
        raise PdfSanitizationError("sanitized PDF visual samples changed")
    return PdfSanitizationResult(
        content=sanitized,
        original_digest=original_digest,
        sanitized_digest=hashlib.sha256(sanitized).hexdigest(),
        page_count=len(sanitized_pages),
        text_digest=original_text_digest,
        visual_sample_digest=original_visual_digest,
        visual_sample_pages=[page + 1 for page in visual_pages],
        removed=removed,
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\x00", "")).strip()


def _pages_digest(pages: list[str]) -> str:
    return hashlib.sha256("\n\f\n".join(pages).encode("utf-8")).hexdigest()


def _object(value: object) -> object:
    return value.get_object() if isinstance(value, IndirectObject) else value


def _visual_digest(content: bytes, pages: list[int]) -> str:
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(content)
        digest = hashlib.sha256()
        for page_number in pages:
            page = document[page_number]
            image = page.render(scale=1).to_pil().convert("RGB")
            digest.update(f"{page_number}:{image.width}x{image.height}:".encode("ascii"))
            digest.update(image.tobytes())
            image.close()
            page.close()
        document.close()
        return digest.hexdigest()
    except Exception as exc:
        raise PdfSanitizationError("PDF visual sample rendering failed") from exc
