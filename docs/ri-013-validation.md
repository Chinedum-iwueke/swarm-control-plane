# RI-013 Bounded Iterative Ingestion Recovery Validation

## Scope

RI-013 extends the VM2 Research Ingestion Recovery Steward with a finite recovery
controller and an advisory-only Codex boundary. It does not change canonical evidence
authority, scanner authority, or the normal scientific-ingestion publication path.

## Implemented controls

- Each artifact receives at most one structural-repair, independent-parser and offline
  OCR attempt.
- Receipts retain method, timestamps, failure category, derived digest and pipeline
  status.
- Codex receives bounded diagnostics only and returns a strict enum-based plan.
- Unavailable, malformed, failed or unsafe advice falls back to deterministic policy.
- Neither the advice schema nor the Codex process has a publication or scanner-control
  action.
- Only the existing scientific-ingestion pipeline can publish recovered evidence.
- Terminal classifications carry a bounded founder action. Security-blocked content
  creates a non-executable provenance-redaction proposal requiring founder approval.
- Legacy unresolved recovery records are adopted once into the new controller without
  deleting their earlier attempt evidence.

## Local validation

- Backend: 280 tests passed.
- Worker: 192 tests passed with the worker virtual environment first on `PATH`.
- Focused Ruff checks passed for every changed Python module and test.
- Python compileall passed for backend and worker sources.
- The recovery systemd unit passed local verification; the host emitted only its known
  unrelated snapd `RestartMode` warning and a netplan permission diagnostic.

## Production gate

Production qualification requires rebuilding the VM2 API image, creating a dedicated
UID-10001 Codex home, completing device authentication, installing package version
1.1.0, and observing terminal receipts for the retained Cartea and `2505.22954v3.pdf`
quarantines. Expected classifications are respectively `replacement_required` and
`security_blocked`. Until those receipts exist, RI-013 is implemented but not
production-qualified.
