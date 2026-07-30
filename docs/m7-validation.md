# M7 Mac Mission Control Validation

Date: 2026-07-30

## Scope

M7 introduces a Mac-local founder interface for:

- control-plane health and portfolio status;
- agent, task, approval, artifact, and control-scope visibility;
- structured founder task and mission intake;
- explicit approval and rejection decisions;
- private Markdown/text ingestion;
- deterministic full-text retrieval with source citations;
- a provenance-bound graph from document titles, wiki links, and tags.

## Security controls

- loopback-only bind is enforced in configuration;
- the operator token is read from a mode-`0600` file and is never returned to
  the browser;
- browser mutations require a non-simple founder-action header;
- intake models reject unknown fields and do not accept command strings;
- founder requests require the unavailable `founder-intake` capability on the
  unavailable `control-plane-planner` machine;
- current engineering and infrastructure workers are ineligible;
- knowledge remains in a mode-`0600` Mac-local SQLite database;
- ingestion accepts only UTF-8 Markdown/text under configured roots;
- path traversal, relative paths, symlink escapes, unsupported formats, and
  files above 5 MiB are rejected;
- citations contain source path, exact line range, modification timestamp, and
  document SHA-256;
- no knowledge content is sent to the control plane or an external model.

## Automated evidence

- Mission Control: 20 tests passed;
- Mission Control Ruff and compileall passed;
- browser JavaScript syntax check passed;
- macOS installer and uninstaller passed `bash -n`;
- desktop and mobile Chromium renders were inspected without overlap;
- worker regression suite: 116 passed;
- backend contract suite: 20 passed.

Repository-wide backend Ruff continues to report the existing import-order and
broad health-boundary findings documented during M5/M6. M7 changes no backend
files.

## Operational evidence

Pending Git promotion and the supervised Mac pilot in
`docs/runbooks/m7-mac-mission-control.md`.

## Pilot limitations

- no PDF, OCR, email, cloud-drive, embedding, or model-answer connector;
- graph extraction is explicit and deterministic rather than model-generated;
- artifact metadata is visible, but remote artifact bytes are not downloaded;
- founder intake queues a planner contract; M7 deploys no planner worker;
- the control plane currently has one orchestrator credential class rather
  than a narrower founder-only token;
- the interface is single-founder and loopback-only.
