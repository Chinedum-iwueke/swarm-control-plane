# M4 Bounded Engineering Mission Runbook

## Scope

M4 accepts a founder-approved, version-controlled milestone manifest and creates
a dependency-gated task DAG. Each ready task runs in a detached Git worktree:

1. an ephemeral Codex coding session may edit only the declared paths;
2. changed paths and file/diff budgets are enforced independently;
3. the reviewed named validation workflow runs;
4. a separate ephemeral Codex review session examines uncommitted changes;
5. the worker produces a patch and PR bundle without push, merge, or deployment.

Task input is structured and rejects command fields. Model-generated commands
run under Codex `workspace-write` sandboxing with child-command network disabled.
The worker token is absent from the coding process environment.

## Dedicated Codex Identity

Do not use the developer's normal Codex home. Provision a dedicated directory:

```bash
sudo install -d -o omenka -g omenka -m 0700 \
  /etc/invariance-swarm/codex-worker
sudo -u omenka env CODEX_HOME=/etc/invariance-swarm/codex-worker \
  /usr/bin/codex login --device-auth
sudo -u omenka env CODEX_HOME=/etc/invariance-swarm/codex-worker \
  /usr/bin/codex login status
```

Set or retain:

```text
SWARM_CODEX_HOME=/etc/invariance-swarm/codex-worker
SWARM_CODEX_MODEL=gpt-5.6-sol
SWARM_ENGINEERING_TIMEOUT_SECONDS=1800
```

The credential is not copied into validation subprocesses. Keep it readable
only by `omenka`, rotate it independently, and revoke it with the worker.

## Deployment

1. Deploy migration `a1d9e5f63c20` and restart the API.
2. Pull the reviewed source on VM1 and reinstall the worker.
3. Reinstall the systemd unit because its Codex path restriction changed.
4. Register role package `vm1-engineering-worker` version `1.0.0`.
5. Bind it to `vm1-developer-coder` and revoke the validation-only binding.
6. Run the non-leasing worker `check`.
7. Keep the continuous daemon stopped for the pilot.

## Submit Pilot

Review `worker/missions/m4-pilot.yaml`, including its approval reference. Then:

```bash
cd /home/omenka/Projects/swarm-control-plane/worker
.venv/bin/python scripts/missions.py create \
  --manifest missions/m4-pilot.yaml
```

The protected operator environment used for `create` must also contain
`SWARM_MISSION_APPROVAL_SECRET`. Keep it in a separate root-owned mode-`0600`
file and do not deploy it to the worker service. The API receives only the
manifest signature.

Run exactly one worker cycle using the protected worker environment. Inspect
with `scripts/missions.py status --mission-id UUID` and
`scripts/governance.py artifacts --task-id UUID`.

## Acceptance

The pilot passes only when:

- the task succeeds with attempt count one;
- only `docs/m4-engineering-pilot-result.md` changed;
- compile and tests passed;
- an independent review exists;
- `changes.patch` and `pr-bundle.json` match registered digests;
- the source checkout is unchanged;
- no push, merge, deployment, or credential access occurred;
- events and results contain no credentials.

Apply the patch through normal human review. M4 does not push or open a GitHub
PR automatically. Preserve the workspace until the bundle is accepted.
