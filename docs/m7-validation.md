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

### Deployment

- source merged through PR 14; Python 3.9 startup fix merged through PR 15;
- deployed source: `4de5c97`;
- Mac: macOS 15.7.3, Intel, Apple Python 3.9.6;
- authenticated `check` succeeded against the VM2 control plane;
- launch agent: `com.invariance.hermes-mission-control`;
- service state: running;
- listener: `127.0.0.1:8790` only;
- orchestrator token: mode `0600`, owner `ice:staff`;
- knowledge database: mode `0600`, owner `ice:staff`;
- control-plane dashboard health: `ok`.

### Knowledge pilot

- reviewed corpus source: `docs/hermes-swarm-system-design.md`;
- source digest:
  `ec3fd2dff72119fc028e57b8494f6831e4943ac1fd4bae77ce9766b00e930690`;
- indexed chunks: 206;
- cited query: `bounded specialization`;
- citation:
  `/Users/ice/Projects/swarm-control-plane/docs/hermes-swarm-system-design.md#L30-L30`;
- private pilot note digest:
  `9a04c73d6f679ab10c9c2d083b76c9aafadaa22b5db81b0482e7fe3e9c048496`;
- graph: 7 nodes and 5 explicit relationships;
- graph entities included Hermes Swarm, Mission Control, Control Plane, Mac
  Founder, and knowledge.

No model or cloud connector processed the corpus. macOS correctly denied
launchd access to `~/Documents` without Full Disk Access. The pilot source was
moved to the application-private data directory, and the product default was
updated accordingly.

### Founder intake pilot

- task: `48210932-1972-481d-a91c-2bdcb67d679b`;
- task number: `FOUNDER-MISSION-20260730T122748527432Z`;
- task type: `founder_request`;
- request kind: `mission`;
- risk level: 0;
- required capability: `founder-intake`;
- allowed machine: `control-plane-planner`;
- event sequence: `task_created`;
- delayed state: queued, attempt 0, no assigned agent.

The deployed VM1 engineering worker, VM2 infrastructure worker, and VM2
lifecycle validator match neither the capability nor machine restriction.
Knowledge title/path content was absent from the task and event record. The
operator token was absent from task/events and Mission Control logs.

## Recommendation

M7 is operationally complete for its bounded pilot. Mission Control is suitable
for daily loopback-only status, approval, structured intake, and private text
search. Broader corpus connectors and model-generated research intelligence
remain later milestones.

## Pilot limitations

- no PDF, OCR, email, cloud-drive, embedding, or model-answer connector;
- graph extraction is explicit and deterministic rather than model-generated;
- artifact metadata is visible, but remote artifact bytes are not downloaded;
- founder intake queues a planner contract; M7 deploys no planner worker;
- the control plane currently has one orchestrator credential class rather
  than a narrower founder-only token;
- the interface is single-founder and loopback-only.
