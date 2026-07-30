# M7 Mac Mission Control Pilot

## Objective

Validate the Mac as a founder-facing control and private-knowledge surface
without granting it production execution authority.

## Preconditions

- M5/M6 changes are merged;
- the Mac pulls reviewed source from GitHub;
- SSH access from VM1 is available;
- the protected operator token is staged without printing it;
- Mission Control binds to loopback only;
- the configured knowledge root contains a non-sensitive pilot Markdown file.

## Source validation

```bash
cd mission-control
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m compileall -q src
pytest -q
ruff check src tests
bash -n macos/install.sh macos/uninstall.sh
```

## Mac installation

Follow `mission-control/README.md`. Run `check` before starting launchd. Do not
expose port 8790 beyond loopback.

## Pilot

1. Open the dashboard and confirm control-plane health, tasks, agents,
   approvals, artifacts, and control scopes load.
2. Index one approved Markdown source under the configured knowledge root.
3. Search for a known phrase and verify the result cites the source path, line
   range, modification time, and digest.
4. Confirm the graph includes the document and its explicit wiki-link/tag
   entities.
5. Submit one low-risk founder request and verify it becomes a structured
   `founder_request` with `founder-intake` capability and
   `control-plane-planner` machine restriction.
6. Do not deploy a matching planner worker in this milestone.
7. Confirm existing engineering and infrastructure workers do not lease the
   request.

## Evidence

Record:

- reviewed source commit;
- Mac Python and application version;
- check-command output;
- local service status;
- indexed source digest and citation;
- graph node/relationship counts;
- founder-request task ID and exact structured contract;
- control-plane event sequence;
- confirmation that document text is absent from task/event records;
- confirmation that port 8790 listens only on loopback.

## Stop conditions

Stop if the token appears in output, the server binds non-loopback, a source
outside approved roots is accepted, knowledge text leaves the Mac, or a current
worker leases the founder request.

