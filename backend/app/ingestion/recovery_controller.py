from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

RecoveryMethod = Literal[
    "structural_repair",
    "independent_parser",
    "offline_ocr",
]
TerminalClassification = Literal[
    "replacement_required",
    "security_blocked",
    "unsupported_format",
    "corrupt_unrecoverable",
    "manual_review_required",
]


class RecoveryDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str = Field(max_length=180)
    media_type: str = Field(max_length=100)
    rejection_stage: str = Field(max_length=80)
    rejection_reason: str = Field(max_length=500)
    attempted_methods: list[RecoveryMethod] = Field(max_length=3)
    available_methods: list[RecoveryMethod] = Field(max_length=3)


class RecoveryAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal[
        "try_structural_repair",
        "try_independent_parser",
        "try_offline_ocr",
        "classify_terminal",
    ]
    terminal_classification: TerminalClassification | None
    rationale: str = Field(min_length=1, max_length=500)


class RecoveryAdviser(Protocol):
    def advise(self, diagnostic: RecoveryDiagnostic) -> RecoveryAdvice: ...


class CodexRecoveryAdviser:
    """Advisory-only Codex boundary with no artifact, database, or tool access."""

    def __init__(
        self,
        *,
        binary: Path,
        codex_home: Path,
        model: str,
        timeout_seconds: float = 90,
    ) -> None:
        self._binary = binary
        self._codex_home = codex_home
        self._model = model
        self._timeout = timeout_seconds

    def advise(self, diagnostic: RecoveryDiagnostic) -> RecoveryAdvice:
        with tempfile.TemporaryDirectory(prefix="recovery-advice-") as temporary:
            root = Path(temporary)
            schema = root / "advice.schema.json"
            output = root / "advice.json"
            schema.write_text(
                json.dumps(_strict_schema(RecoveryAdvice.model_json_schema())),
                encoding="utf-8",
            )
            process = subprocess.Popen(
                [
                    str(self._binary),
                    "exec",
                    "--sandbox",
                    "read-only",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--skip-git-repo-check",
                    "--model",
                    self._model,
                    "--output-schema",
                    str(schema),
                    "--output-last-message",
                    str(output),
                    "-C",
                    str(root),
                    "-",
                ],
                stdin=subprocess.PIPE,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": str(self._codex_home),
                    "CODEX_HOME": str(self._codex_home),
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                },
                start_new_session=True,
            )
            try:
                process.communicate(_prompt(diagnostic), timeout=self._timeout)
            except subprocess.TimeoutExpired as exc:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise RuntimeError("Codex recovery advice timed out safely.") from exc
            if process.returncode != 0:
                raise RuntimeError("Codex recovery advice failed safely.")
            return RecoveryAdvice.model_validate_json(
                output.read_text(encoding="utf-8")
            )


def select_next_method(
    diagnostic: RecoveryDiagnostic,
    adviser: RecoveryAdviser | None,
) -> tuple[RecoveryMethod | None, RecoveryAdvice | None]:
    advice = None
    if adviser is not None:
        try:
            advice = adviser.advise(diagnostic)
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError):
            advice = None
    mapping: dict[str, RecoveryMethod] = {
        "try_structural_repair": "structural_repair",
        "try_independent_parser": "independent_parser",
        "try_offline_ocr": "offline_ocr",
    }
    advised = mapping.get(advice.action) if advice is not None else None
    if advised in diagnostic.available_methods:
        return advised, advice
    if diagnostic.available_methods:
        return diagnostic.available_methods[0], advice
    return None, advice


def deterministic_terminal_classification(
    *, rejection_reason: str, attempted_methods: list[str]
) -> TerminalClassification:
    reason = rejection_reason.lower()
    if "instruction-injection" in reason or "malware" in reason or "secret" in reason:
        return "security_blocked"
    if "media type" in reason or "archive" in reason:
        return "unsupported_format"
    if set(attempted_methods) >= {
        "structural_repair",
        "independent_parser",
        "offline_ocr",
    }:
        return "replacement_required"
    if "unreadable" in reason or "parser rejected" in reason:
        return "corrupt_unrecoverable"
    return "manual_review_required"


def _prompt(diagnostic: RecoveryDiagnostic) -> str:
    return (
        "You are an advisory-only scientific-ingestion recovery planner. "
        "You cannot inspect artifact bytes, execute tools, suppress security findings, "
        "or authorize publication. Choose only an available deterministic method, or "
        "recommend a terminal classification. A scanner finding always remains binding. "
        "Return only the required JSON. Diagnostics:\n" + diagnostic.model_dump_json()
    )


def _strict_schema(value: object) -> object:
    if isinstance(value, dict):
        result = {key: _strict_schema(item) for key, item in value.items()}
        properties = result.get("properties")
        if isinstance(properties, dict):
            result["additionalProperties"] = False
            result["required"] = list(properties)
        return result
    if isinstance(value, list):
        return [_strict_schema(item) for item in value]
    return value
