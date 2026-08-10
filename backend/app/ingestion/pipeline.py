from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

_ACTIVE_PDF_MARKERS = (
    b"/JavaScript",
    b"/JS",
    b"/OpenAction",
    b"/Launch",
    b"/EmbeddedFile",
    b"/AA",
)
_EICAR = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"reveal\s+(the\s+)?system\s+prompt",
        r"override\s+(your\s+)?(policy|instructions)",
        r"exfiltrate\s+(credentials|secrets|tokens)",
        r"(?:read|send|upload|print)\s+(?:the\s+)?(?:contents\s+of\s+)?/(?:run|etc)/secrets",
        r"(?:approve|authorize)\s+(?:this|the)\s+(?:task|mission|request)",
        r"(?:execute|run|call)\s+(?:this\s+)?(?:tool|command|shell)",
        r"treat\s+(?:this|the following)\s+(?:text\s+)?as\s+(?:a\s+)?system\s+instruction",
    )
)
_HEADING = re.compile(r"^(?:[0-9]+(?:\.[0-9]+)*[.)]?\s+|#{1,6}\s+)(.+)$")
_EQUATION = re.compile(r"(?:^|\s)[A-Za-z][A-Za-z0-9_]*\s*=\s*[^=]+")
_FIGURE = re.compile(r"^(?:figure|fig\.)\s*[0-9]+", re.IGNORECASE)
_CITATION = re.compile(r"(?:\[[0-9]+\]|doi:\s*10\.[0-9]{4,9}/\S+)", re.IGNORECASE)


class IngestionRejected(ValueError):
    """The artifact cannot safely proceed beyond quarantine."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "validate",
        remediation: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.remediation = remediation


class OcrAdapter(Protocol):
    name: str
    network_access: bool

    def recover_pages(self, content: bytes) -> list[str]: ...


class MalwareScanner(Protocol):
    name: str

    def scan(self, content: bytes) -> str | None: ...


class BuiltinSignatureScanner:
    name = "builtin-signatures-v1"

    def scan(self, content: bytes) -> str | None:
        if _EICAR in content:
            return "malware test signature detected"
        return None


@dataclass(frozen=True)
class RecoveredObject:
    scientific_type: str
    page: int
    line_start: int
    line_end: int
    text: str
    confidence: float
    parent_index: int | None = None


@dataclass(frozen=True)
class RecoveryReport:
    media_type: str
    parser: str
    scanner: str
    scanned: bool
    page_count: int
    objects: list[RecoveredObject]
    warnings: list[str] = field(default_factory=list)


class ScientificIngestionPipeline:
    def __init__(
        self,
        *,
        ocr: OcrAdapter | None = None,
        malware_scanner: MalwareScanner | None = None,
        max_bytes: int = 25 * 1024 * 1024,
        max_pages: int = 2000,
        max_expansion_ratio: int = 100,
        minimum_confidence: float = 0.65,
    ) -> None:
        self.ocr = ocr
        self.malware_scanner = malware_scanner or BuiltinSignatureScanner()
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_expansion_ratio = max_expansion_ratio
        self.minimum_confidence = minimum_confidence

    def recover(self, filename: str, media_type: str, content: bytes) -> RecoveryReport:
        self._inspect_container(filename, media_type, content)
        if media_type == "application/pdf":
            pages, scanned, parser = self._pdf_pages(content)
        else:
            pages, scanned, parser = self._text_pages(content)
        combined = "\n".join(pages)
        if len(combined.encode("utf-8")) > max(1, len(content)) * self.max_expansion_ratio:
            raise IngestionRejected(
                "extracted content exceeds the expansion limit", stage="extract"
            )
        if contains_instruction_injection(combined):
            raise IngestionRejected("document contains instruction-injection content")
        objects = self._recover_objects(pages, scanned=scanned)
        if not objects:
            raise IngestionRejected(
                "document recovery produced no scientific objects", stage="recover"
            )
        if min(item.confidence for item in objects) < self.minimum_confidence:
            raise IngestionRejected(
                "recovery confidence is below the publication floor",
                remediation=True,
            )
        return RecoveryReport(
            media_type=media_type,
            parser=parser,
            scanner=self.malware_scanner.name,
            scanned=scanned,
            page_count=len(pages),
            objects=objects,
            warnings=["ocr-derived content requires review"] if scanned else [],
        )

    def _inspect_container(self, filename: str, media_type: str, content: bytes) -> None:
        if not content or len(content) > self.max_bytes:
            raise IngestionRejected(
                "artifact size is outside the ingestion limit", stage="quarantine"
            )
        malware_finding = self.malware_scanner.scan(content)
        if malware_finding is not None:
            raise IngestionRejected(malware_finding, stage="scan")
        suffix = Path(filename).suffix.lower()
        allowed = {
            "application/pdf": {".pdf"},
            "text/plain": {".txt"},
            "text/markdown": {".md", ".markdown"},
        }
        if media_type not in allowed or suffix not in allowed[media_type]:
            raise IngestionRejected(
                "declared media type and filename are incompatible", stage="scan"
            )
        if content.startswith((b"PK\x03\x04", b"Rar!")):
            raise IngestionRejected(
                "archives are not accepted by scientific ingestion", stage="scan"
            )
        if media_type == "application/pdf":
            if not content.startswith(b"%PDF-"):
                raise IngestionRejected("PDF signature is invalid", stage="scan")
            if any(marker in content for marker in _ACTIVE_PDF_MARKERS):
                raise IngestionRejected("active PDF content is forbidden", stage="scan")

    def _pdf_pages(self, content: bytes) -> tuple[list[str], bool, str]:
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if len(reader.pages) == 0 or len(reader.pages) > self.max_pages:
                raise IngestionRejected(
                    "PDF page count is outside the ingestion limit", stage="extract"
                )
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except IngestionRejected:
            raise
        except Exception as exc:
            raise IngestionRejected(
                "PDF parser rejected the artifact", stage="extract"
            ) from exc
        if any(pages):
            return pages, False, f"pypdf-{__import__('pypdf').__version__}"
        if self.ocr is None:
            raise IngestionRejected(
                "scanned PDF requires an approved OCR adapter",
                stage="extract",
                remediation=True,
            )
        if getattr(self.ocr, "network_access", True):
            raise IngestionRejected(
                "OCR adapter must declare network_access false", stage="extract"
            )
        pages = [item.strip() for item in self.ocr.recover_pages(content)]
        if not pages or not any(pages) or len(pages) > self.max_pages:
            raise IngestionRejected(
                "OCR recovery produced no bounded page content",
                stage="extract",
                remediation=True,
            )
        return pages, True, self.ocr.name

    def _text_pages(self, content: bytes) -> tuple[list[str], bool, str]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise IngestionRejected(
                "text artifact must be valid UTF-8", stage="extract"
            ) from exc
        return [text.strip()], False, "utf8-text-v1"

    def _recover_objects(
        self, pages: list[str], *, scanned: bool
    ) -> list[RecoveredObject]:
        output: list[RecoveredObject] = []
        current_section: int | None = None
        base_confidence = 0.78 if scanned else 0.98
        for page_number, text in enumerate(pages, 1):
            lines = text.splitlines()
            paragraph_start: int | None = None
            paragraph_lines: list[str] = []

            def flush_paragraph(
                end_line: int, parent_index: int | None, page: int
            ) -> None:
                nonlocal paragraph_start, paragraph_lines
                if paragraph_start is None or not paragraph_lines:
                    paragraph_start, paragraph_lines = None, []
                    return
                paragraph = "\n".join(paragraph_lines).strip()
                if paragraph:
                    output.append(
                        RecoveredObject(
                            scientific_type="paragraph",
                            page=page,
                            line_start=paragraph_start,
                            line_end=end_line,
                            text=paragraph,
                            confidence=base_confidence,
                            parent_index=parent_index,
                        )
                    )
                paragraph_start, paragraph_lines = None, []

            for line_number, raw in enumerate(lines, 1):
                line = raw.strip()
                if not line:
                    flush_paragraph(line_number - 1, current_section, page_number)
                    continue
                heading = _HEADING.match(line)
                object_type = self._line_object_type(line)
                if heading:
                    flush_paragraph(line_number - 1, current_section, page_number)
                    output.append(
                        RecoveredObject(
                            scientific_type="section",
                            page=page_number,
                            line_start=line_number,
                            line_end=line_number,
                            text=heading.group(1),
                            confidence=base_confidence,
                        )
                    )
                    current_section = len(output) - 1
                elif object_type is not None:
                    flush_paragraph(line_number - 1, current_section, page_number)
                    output.append(
                        RecoveredObject(
                            scientific_type=object_type,
                            page=page_number,
                            line_start=line_number,
                            line_end=line_number,
                            text=line,
                            confidence=base_confidence - (0.08 if scanned else 0),
                            parent_index=current_section,
                        )
                    )
                else:
                    if paragraph_start is None:
                        paragraph_start = line_number
                    paragraph_lines.append(line)
            flush_paragraph(len(lines), current_section, page_number)
        return output

    @staticmethod
    def _line_object_type(line: str) -> str | None:
        if line.count("|") >= 2 or re.search(r"\S+\s{2,}\S+\s{2,}\S+", line):
            return "table"
        if _FIGURE.match(line):
            return "figure"
        if _CITATION.search(line):
            return "citation"
        if _EQUATION.search(line):
            return "equation"
        if line.lower().startswith(("note:", "footnote:")):
            return "note"
        return None


def contains_instruction_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)
