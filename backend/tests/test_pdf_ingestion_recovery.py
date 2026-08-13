from __future__ import annotations

from io import BytesIO

import pytest
from app.ingestion.pdf_sanitizer import PdfSanitizationError, sanitize_pdf
from app.ingestion.pipeline import ScientificIngestionPipeline, _has_active_pdf_content
from pypdf import PdfReader, PdfWriter

from tests.test_scientific_ingestion import golden_pdf


def active_text_pdf() -> bytes:
    reader = PdfReader(BytesIO(golden_pdf()), strict=True)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.add_js("app.alert('publisher navigation')")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_active_pdf_is_rewritten_as_inert_text_equivalent_edition() -> None:
    original = active_text_pdf()
    assert _has_active_pdf_content(PdfReader(BytesIO(original), strict=True))

    result = sanitize_pdf(original)

    assert result.original_digest != result.sanitized_digest
    assert result.page_count == 1
    assert result.text_digest
    assert result.visual_sample_digest
    assert result.visual_sample_pages == [1]
    assert result.removed["names"] == 1
    sanitized = PdfReader(BytesIO(result.content), strict=True)
    assert not _has_active_pdf_content(sanitized)
    report = ScientificIngestionPipeline().recover(
        "recovered.pdf", "application/pdf", result.content
    )
    assert report.page_count == 1
    assert report.objects


def test_sanitizer_is_deterministic() -> None:
    original = active_text_pdf()
    first = sanitize_pdf(original)
    second = sanitize_pdf(original)
    assert first.sanitized_digest == second.sanitized_digest
    assert first.content == second.content


def test_sanitizer_rejects_unparseable_pdf() -> None:
    with pytest.raises(PdfSanitizationError, match="cannot be parsed"):
        sanitize_pdf(b"%PDF-1.4\nbroken")


def test_sanitizer_never_mutates_original_bytes() -> None:
    original = active_text_pdf()
    retained = bytes(original)
    sanitize_pdf(original)
    assert original == retained
