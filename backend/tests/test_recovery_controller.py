from __future__ import annotations

from pathlib import Path

from app.ingestion.recovery_controller import (
    CodexRecoveryAdviser,
    RecoveryAdvice,
    RecoveryDiagnostic,
    deterministic_terminal_classification,
    select_next_method,
)


class StubAdviser:
    def __init__(self, advice: RecoveryAdvice) -> None:
        self.advice = advice

    def advise(self, diagnostic: RecoveryDiagnostic) -> RecoveryAdvice:
        return self.advice


def diagnostic(*, attempted: list[str] | None = None) -> RecoveryDiagnostic:
    attempted = attempted or []
    methods = [
        item
        for item in ("structural_repair", "independent_parser", "offline_ocr")
        if item not in attempted
    ]
    return RecoveryDiagnostic(
        filename="research.pdf",
        media_type="application/pdf",
        rejection_stage="extract",
        rejection_reason="PDF parser rejected the artifact",
        attempted_methods=attempted,
        available_methods=methods,
    )


def test_codex_can_select_only_an_available_deterministic_method() -> None:
    adviser = StubAdviser(
        RecoveryAdvice(
            action="try_offline_ocr",
            terminal_classification=None,
            rationale="Independent parsing already failed.",
        )
    )

    method, advice = select_next_method(
        diagnostic(attempted=["structural_repair", "independent_parser"]), adviser
    )

    assert method == "offline_ocr"
    assert advice is adviser.advice


def test_unavailable_codex_method_cannot_bypass_controller_order() -> None:
    adviser = StubAdviser(
        RecoveryAdvice(
            action="try_structural_repair",
            terminal_classification=None,
            rationale="Try the structural method.",
        )
    )

    method, _ = select_next_method(diagnostic(attempted=["structural_repair"]), adviser)

    assert method == "independent_parser"


def test_adviser_failure_falls_back_to_deterministic_method() -> None:
    adviser = CodexRecoveryAdviser(
        binary=Path("/definitely/missing/codex"),
        codex_home=Path("/definitely/missing/home"),
        model="test-model",
    )

    method, advice = select_next_method(diagnostic(), adviser)

    assert method == "structural_repair"
    assert advice is None


def test_instruction_injection_is_always_security_blocked() -> None:
    assert (
        deterministic_terminal_classification(
            rejection_reason="document contains instruction-injection content",
            attempted_methods=["structural_repair"],
        )
        == "security_blocked"
    )


def test_exhausted_corrupt_pdf_requires_replacement() -> None:
    assert (
        deterministic_terminal_classification(
            rejection_reason="offline OCR could not render the PDF",
            attempted_methods=[
                "structural_repair",
                "independent_parser",
                "offline_ocr",
            ],
        )
        == "replacement_required"
    )


def test_codex_advice_schema_has_no_publication_action() -> None:
    actions = RecoveryAdvice.model_json_schema()["properties"]["action"]
    assert "publish" not in str(actions).lower()
    assert "suppress" not in str(actions).lower()
