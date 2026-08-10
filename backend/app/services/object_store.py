from __future__ import annotations

from dataclasses import dataclass
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
