from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol


@dataclass(frozen=True)
class ObjectReference:
    uri: str
    content_digest: str
    byte_size: int


class EvidenceObjectStore(Protocol):
    """Binary evidence storage boundary; canonical metadata remains in PostgreSQL."""

    def put(self, content: bytes, *, expected_digest: str) -> ObjectReference: ...

    def get(self, reference: ObjectReference) -> bytes: ...

    def exists(self, reference: ObjectReference) -> bool: ...


class FilesystemEvidenceObjectStore:
    """Content-addressed local adapter with traversal and digest protection."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, content: bytes, *, expected_digest: str) -> ObjectReference:
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected_digest:
            raise ValueError("object-store content digest mismatch")
        target = self._path(actual)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != actual:
                raise ValueError("object-store existing content is corrupt")
        else:
            with NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            temporary.chmod(0o600)
            os.replace(temporary, target)
        return ObjectReference(
            uri=f"evidence://sha256/{actual}",
            content_digest=actual,
            byte_size=len(content),
        )

    def get(self, reference: ObjectReference) -> bytes:
        content = self._path(reference.content_digest).read_bytes()
        if hashlib.sha256(content).hexdigest() != reference.content_digest:
            raise ValueError("object-store content digest mismatch")
        return content

    def exists(self, reference: ObjectReference) -> bool:
        return self._path(reference.content_digest).is_file()

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("object-store digest is invalid")
        path = (self.root / digest[:2] / digest[2:]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("object-store path escapes root")
        return path
