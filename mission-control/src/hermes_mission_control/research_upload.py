from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


class ResearchUploadError(ValueError):
    """The uploaded source violates the research intake policy."""


@dataclass(frozen=True)
class Passage:
    ordinal: int
    section: str
    page: int | None
    line_start: int
    line_end: int
    text: str


_SAFE = re.compile(r"[^a-z0-9._-]+")


def safe_filename(name: str) -> str:
    leaf = Path(name).name
    cleaned = _SAFE.sub("-", leaf.lower()).strip(".-")
    if not cleaned or cleaned.startswith("."):
        raise ResearchUploadError("The source filename is unsafe.")
    return cleaned[:180]


def extract_passages(filename: str, content: bytes) -> list[Passage]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        try:
            pages = [
                page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages
            ]
        except Exception as exc:  # pypdf exposes several parser-specific errors
            raise ResearchUploadError("The PDF could not be parsed safely.") from exc
        passages = []
        ordinal = 0
        for page_number, text in enumerate(pages, 1):
            for start, chunk in _chunks(text):
                passages.append(
                    Passage(
                        ordinal,
                        f"Page {page_number}",
                        page_number,
                        start,
                        start + chunk.count("\n"),
                        chunk,
                    )
                )
                ordinal += 1
        if not passages:
            raise ResearchUploadError("The PDF contains no extractable text.")
        return passages
    if suffix not in {".md", ".markdown", ".txt"}:
        raise ResearchUploadError("Only PDF, Markdown, and text sources are accepted.")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResearchUploadError("Text sources must use UTF-8.") from exc
    return [
        Passage(index, "Document", None, start, start + chunk.count("\n"), chunk)
        for index, (start, chunk) in enumerate(_chunks(text))
    ]


def _chunks(text: str, limit: int = 6000) -> list[tuple[int, str]]:
    lines = text.splitlines()
    output: list[tuple[int, str]] = []
    start = 1
    buffer: list[str] = []
    size = 0
    for number, line in enumerate(lines, 1):
        if buffer and size + len(line) + 1 > limit:
            output.append((start, "\n".join(buffer).strip()))
            buffer, size, start = [], 0, number
        if line.strip() or buffer:
            buffer.append(line)
            size += len(line) + 1
    if buffer:
        output.append((start, "\n".join(buffer).strip()))
    return [(start, chunk) for start, chunk in output if chunk]


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
