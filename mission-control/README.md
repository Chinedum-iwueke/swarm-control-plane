# Hermes Mission Control

Hermes Mission Control is the Mac-local founder surface for the swarm. It
combines control-plane status, structured request intake, approval decisions,
artifact visibility, and a private cited-search pilot.

## Security boundary

- The server binds only to `127.0.0.1` by default.
- The orchestrator token is read from a mode-`0600` file and never reaches the
  browser.
- Mutating browser requests require a custom founder-action header.
- Intake creates a structured `founder_request`; it cannot carry commands.
- Requests target the future `control-plane-planner` capability and cannot be
  leased by current engineering or infrastructure workers.
- Knowledge documents remain in a Mac-local SQLite database.
- Only UTF-8 Markdown and text files beneath explicitly configured roots can be
  indexed.
- Symlink escapes, relative paths, unsupported files, and files above 5 MiB are
  rejected.
- Search is deterministic full-text retrieval. Every result includes the
  original path, source line range, modification time, and SHA-256 digest.
- No document content is sent to the control plane or an external model.

## Configuration

Create the application directory and token file on the Mac:

```bash
install -d -m 0700 "$HOME/Library/Application Support/Hermes Mission Control"
install -m 0600 /path/to/staged/operator-token \
  "$HOME/Library/Application Support/Hermes Mission Control/orchestrator.token"
```

Create
`~/Library/Application Support/Hermes Mission Control/mission-control.env`:

```bash
cat >"$HOME/Library/Application Support/Hermes Mission Control/mission-control.env" <<'EOF'
HERMES_API_URL=http://100.112.117.59:8787
HERMES_ORCHESTRATOR_TOKEN_FILE="/Users/ice/Library/Application Support/Hermes Mission Control/orchestrator.token"
HERMES_DATA_ROOT="/Users/ice/Library/Application Support/Hermes Mission Control/data"
HERMES_KNOWLEDGE_ROOTS=/Users/ice/Documents
HERMES_HOST=127.0.0.1
HERMES_PORT=8790
EOF
chmod 0600 "$HOME/Library/Application Support/Hermes Mission Control/mission-control.env"
```

Multiple knowledge roots use the macOS path separator (`:`).

## Install

Software is authored on VM1, merged to GitHub, and pulled to the Mac:

```bash
cd ~/Projects/swarm-control-plane
git pull --ff-only origin main
cd mission-control
./macos/install.sh
```

The installer does not start the service unless explicitly asked:

```bash
./macos/install.sh --start
```

## Check

```bash
set -a
source "$HOME/Library/Application Support/Hermes Mission Control/mission-control.env"
set +a
"$HOME/Library/Application Support/Hermes Mission Control/venv/bin/hermes-mission-control" check
```

## Operate

Open <http://127.0.0.1:8790>. Inspect launchd and local logs with:

```bash
launchctl print "gui/$UID/com.invariance.hermes-mission-control"
tail -f "$HOME/Library/Application Support/Hermes Mission Control/mission-control.log"
tail -f "$HOME/Library/Application Support/Hermes Mission Control/mission-control.error.log"
```

Index a source by entering its absolute path in Knowledge Explorer. The source
must be under `HERMES_KNOWLEDGE_ROOTS`.

## Token rotation

1. Stage the replacement token without printing it.
2. Replace `orchestrator.token` atomically with mode `0600`.
3. Restart the launch agent.
4. Revoke the old token at the control plane after the check succeeds.

The current control plane uses one orchestrator credential. M7 therefore
requires a protected copy on the Mac. A scoped founder credential is a
recommended follow-up before broader rollout.

## Uninstall and rollback

```bash
./macos/uninstall.sh --stop
```

The uninstall script removes only the launchd definition. It preserves
credentials, the private database, logs, and the virtual environment. Restore
an earlier reviewed Git revision and rerun the installer to roll back software.

## Pilot limitations

- The knowledge pilot supports local Markdown and text, not PDF, email, cloud
  drives, embeddings, OCR, or model-generated answers.
- The graph is explicit and deterministic: document titles, `[[wiki links]]`,
  and `#tags`.
- Artifact metadata is visible, but workspace artifact bytes are not remotely
  downloaded.
- Intake is a planner queue contract; no autonomous planner is deployed in M7.
- The UI is single-founder and loopback-only.
