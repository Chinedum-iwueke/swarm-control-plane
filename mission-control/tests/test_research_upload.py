from io import BytesIO

import pytest
from pypdf import PdfWriter

from hermes_mission_control.research_upload import (
    ResearchUploadError,
    extract_passages,
    safe_filename,
)


def test_text_upload_preserves_line_citations() -> None:
    passages = extract_passages("paper.md", b"alpha\nbeta\ngamma")
    assert passages[0].text == "alpha\nbeta\ngamma"
    assert passages[0].line_start == 1
    assert passages[0].line_end == 3


def test_pdf_without_extractable_text_is_rejected() -> None:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    with pytest.raises(ResearchUploadError, match="no extractable text"):
        extract_passages("book.pdf", output.getvalue())


@pytest.mark.parametrize("name", ["../paper.pdf", "/tmp/paper.pdf", "paper.PDF"])
def test_filename_is_reduced_to_safe_leaf(name: str) -> None:
    assert safe_filename(name) == "paper.pdf"


def test_unsupported_upload_is_rejected() -> None:
    with pytest.raises(ResearchUploadError, match="Only PDF"):
        extract_passages("archive.zip", b"not an archive")
